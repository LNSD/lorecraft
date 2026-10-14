#!/usr/bin/env python3
"""Classify open pull requests against their base, and with `--apply` bring the ones that are behind up to date.

    sync.py [--apply] PR...

Each pull request is `up_to_date`, `behind` (its base moved and it rebases cleanly), `conflicting` (it does not
rebase cleanly) or `base_moved` (its base is another branch of a stack, so the stack is restacked instead).
`--apply` takes each `behind` one through the fast lane: mark it draft, rebase it onto `origin/main` signing every
commit, run the gates, check the signatures, push with a lease and mark it ready. Prints one JSON result. Never
resolves a conflict, never pushes an unsigned commit, never uses plain `--force`, never merges or closes a PR.
Exit codes: 0 ok, 1 a gate failed, 2 a PR is conflicting or its base moved, 3 refused or a command failed.
"""

import argparse
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Final

# `gitflow` lives in the code-integrate skill, next to this skill's directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'code-integrate' / 'scripts'))

import gitflow  # noqa: E402 — the import needs the `sys.path` line above
from gitflow import EXIT_GATES_FAILED, EXIT_NEEDS_REBASE, EXIT_OK, EXIT_REFUSED, GitError  # noqa: E402 — same

TRUNK: Final[str] = 'main'
type Entries = list[dict[str, object]]


def sync(
    repo: Path, prs: list[int], log: Path, gates: Mapping[str, list[str]], *, apply: bool
) -> tuple[dict[str, object], int]:
    """Classify each pull request and, when asked, bring the `behind` ones up to date, one after the other.

    Args:
        repo: The repository to work in.
        prs: The pull request numbers.
        log: The file raw git, gh and gate output goes to.
        gates: The command of each gate, by name.
        apply: Whether to run the fast lane on each pull request that is behind.

    Returns:
        The result mapping the script prints, and the exit code that goes with it.

    Raises:
        GitError: A git command that must succeed failed.
    """
    gitflow.git(repo, log, 'fetch', 'origin')
    reason = gitflow.require_clean(repo, log)
    if reason:
        return {'status': 'refused', 'reason': reason}, EXIT_REFUSED

    entries: Entries = []
    start_branch = gitflow.git(repo, log, 'branch', '--show-current')
    start_sha = gitflow.git(repo, log, 'rev-parse', 'HEAD')
    try:
        for number in prs:
            entry = _classify(repo, number, log)
            entries.append(entry)
            if entry['status'] == 'refused':
                return {'status': 'refused', 'reason': entry['reason'], 'prs': entries}, EXIT_REFUSED
            if apply and entry['status'] == 'behind':
                failure = _fast_lane(repo, entry, log, gates)
                if failure is not None:
                    return {'status': failure[0], 'prs': entries}, failure[1]
    except GitError as exc:
        return {'status': 'refused', 'reason': str(exc), 'prs': entries}, EXIT_REFUSED
    finally:
        if start_branch:
            gitflow.git(repo, log, 'switch', start_branch)
        else:
            gitflow.git(repo, log, 'switch', '--detach', start_sha)

    stuck = [entry for entry in entries if entry['status'] in ('conflicting', 'base_moved')]
    return {'status': 'needs_rebase' if stuck else 'ok', 'prs': entries}, EXIT_NEEDS_REBASE if stuck else EXIT_OK


def _classify(repo: Path, number: int, log: Path) -> dict[str, object]:
    """The state of one pull request against its base; `refused` when it is not open or its branch is missing.

    Args:
        repo: The repository to look in.
        number: The pull request number.
        log: The file the commands and their output are appended to.

    Returns:
        The pull request's entry for the result, with its `status`.

    Raises:
        GitError: A git command that must succeed failed.
    """
    shown = gitflow.run(repo, log, ['gh', 'pr', 'view', str(number), '--json', 'headRefName,baseRefName,state,isDraft'])
    if shown.returncode != 0:
        return {'pr': number, 'status': 'refused', 'reason': f'gh pr view {number} failed'}
    info = json.loads(shown.stdout)
    head, base = str(info['headRefName']), str(info['baseRefName'])
    entry: dict[str, object] = {'pr': number, 'branch': head, 'draft': info['isDraft']}
    if info['state'] != 'OPEN':
        return {**entry, 'status': 'refused', 'reason': f'PR {number} is {info["state"]}'}
    head_sha = gitflow.rev_parse(repo, log, f'origin/{head}')
    base_sha = gitflow.rev_parse(repo, log, f'origin/{base}')
    if head_sha is None or base_sha is None:
        return {**entry, 'status': 'refused', 'reason': f'origin/{head} or origin/{base} does not exist'}

    entry['old_sha'] = head_sha
    if gitflow.is_ancestor(repo, log, base_sha, head_sha):
        return {**entry, 'status': 'up_to_date'}
    if base != TRUNK:
        return {**entry, 'status': 'base_moved', 'base': base}
    # `merge-tree` exits 1 when the merge would conflict; it touches neither the tree nor the index.
    merged = gitflow.run(repo, log, ['git', 'merge-tree', '--write-tree', base_sha, head_sha])
    return {**entry, 'status': 'behind' if merged.returncode == 0 else 'conflicting'}


def _fast_lane(
    repo: Path, entry: dict[str, object], log: Path, gates: Mapping[str, list[str]]
) -> tuple[str, int] | None:
    """Rebase one pull request onto `origin/main`, check it and push it; None when it was synced.

    The entry is updated in place: its `status` becomes `synced`, or `conflicting` when the rebase stopped. A pull
    request that was already a draft is left a draft; otherwise it is drafted for the run and marked ready again
    only when the run synced it. A failed gate or an unsigned commit leaves the remote branch untouched.

    Args:
        repo: The repository to work in.
        entry: The classified pull request, with its `branch` and `old_sha`.
        log: The file raw output goes to.
        gates: The command of each gate, by name.

    Returns:
        None when the pull request was synced, otherwise the top-level status and the exit code.

    Raises:
        GitError: A git command that must succeed failed.
    """
    number, branch, old_sha = str(entry['pr']), str(entry['branch']), str(entry['old_sha'])
    # Only a pull request this run drafted is marked ready again; one that was a draft stays one.
    drafted_here = not entry['draft']
    if drafted_here and gitflow.run(repo, log, ['gh', 'pr', 'ready', number, '--undo']).returncode != 0:
        entry.update(status='refused', reason=f'gh pr ready {number} --undo failed, nothing was rebased')
        return 'refused', EXIT_REFUSED
    gitflow.git(repo, log, 'switch', '--detach', old_sha)
    rebased = gitflow.run(repo, log, ['git', 'rebase', '-S', f'origin/{TRUNK}'])
    if rebased.returncode != 0:
        # A rebase also stops when a commit cannot be signed; only unmerged files make it a conflict.
        unmerged = gitflow.git(repo, log, 'diff', '--name-only', '--diff-filter=U')
        gitflow.run(repo, log, ['git', 'rebase', '--abort'])
        if not unmerged:
            entry.update(status='refused', reason=f'the rebase of {branch} stopped without a conflict, see the log')
            return 'refused', EXIT_REFUSED
        entry['status'] = 'conflicting'
        return 'needs_rebase', EXIT_NEEDS_REBASE

    new_sha = gitflow.git(repo, log, 'rev-parse', 'HEAD')
    entry['new_sha'] = new_sha
    entry['gates'] = gitflow.run_gates(repo, log, gates)
    if 'fail' in entry['gates'].values():  # type: ignore[attr-defined]
        entry['status'] = 'gates_failed'
        return 'gates_failed', EXIT_GATES_FAILED
    dirty = gitflow.require_clean(repo, log)
    if dirty:
        entry.update(status='gates_failed', reason=f'a gate left the tree changed: {dirty}')
        return 'gates_failed', EXIT_GATES_FAILED
    unsigned = _unsigned_commits(repo, log, f'origin/{TRUNK}', new_sha)
    if unsigned:
        entry.update(status='refused', reason=f'unsigned commits on {branch}: {" ".join(unsigned)}')
        return 'refused', EXIT_REFUSED

    # Push the rebased commit itself, leased on the remote tip the rebase started from, and only then move the
    # local branch: a rejected push leaves the local branch where it was.
    lease = f'--force-with-lease=refs/heads/{branch}:{old_sha}'
    try:
        gitflow.git(repo, log, 'push', lease, 'origin', f'{new_sha}:refs/heads/{branch}')
    except GitError as exc:
        entry.update(status='refused', reason=str(exc))
        if drafted_here:
            # The pull request stays a draft, so the caller knows to mark it ready or retry.
            entry['drafted'] = True
        return 'refused', EXIT_REFUSED
    entry['push'] = 'lease'
    entry['status'] = 'synced'
    if _checked_out_elsewhere(repo, log, branch):
        # Git refuses to move a branch another worktree has checked out; the remote is what matters.
        entry['local_not_moved'] = True
    else:
        # HEAD is detached, so the local branch can be moved even when the caller had it checked out.
        gitflow.git(repo, log, 'branch', '-f', branch, new_sha)
    if drafted_here and gitflow.run(repo, log, ['gh', 'pr', 'ready', number]).returncode != 0:
        entry['ready'] = False
    return None


def _checked_out_elsewhere(repo: Path, log: Path, branch: str) -> bool:
    """Whether a worktree has the local branch checked out; this worktree is detached, so it is another one.

    Args:
        repo: The repository to look in.
        log: The file the command and its output are appended to.
        branch: The local branch.

    Returns:
        True when a worktree holds the branch.

    Raises:
        GitError: A git command that must succeed failed.
    """
    listed = gitflow.git(repo, log, 'worktree', 'list', '--porcelain').splitlines()
    return f'branch refs/heads/{branch}' in listed


def _unsigned_commits(repo: Path, log: Path, base: str, tip: str) -> list[str]:
    """The commits between the base and the tip whose `%G?` is not `G`.

    Args:
        repo: The repository to look in.
        log: The file the command and its output are appended to.
        base: The commit the branch sits on.
        tip: The branch's tip.

    Returns:
        The SHAs of the unsigned commits, newest first.

    Raises:
        GitError: A git command that must succeed failed.
    """
    unsigned: list[str] = []
    for line in gitflow.git(repo, log, 'log', '--format=%H %G?', f'{base}..{tip}').splitlines():
        sha, status = line.split()
        if status != 'G':
            unsigned.append(sha)
    return unsigned


def main(argv: list[str]) -> int:
    """Parse the arguments, sync in the current directory and print the result.

    Args:
        argv: The command-line arguments, after the program name.

    Returns:
        The exit code the script ends with.
    """
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--apply', action='store_true', help='bring each pull request that is behind up to date')
    parser.add_argument('prs', nargs='+', type=int, help='the pull request numbers')
    args = parser.parse_args(argv)

    repo = Path.cwd()
    log = gitflow.default_log(repo, 'code-sync')
    try:
        result, code = sync(repo, args.prs, log, gitflow.default_gates(), apply=args.apply)
    except GitError as exc:
        result, code = {'status': 'error', 'reason': str(exc)}, EXIT_REFUSED
    gitflow.emit(result, log)
    return code


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
