#!/usr/bin/env python3
"""Rebase a stack of part branches onto a new base, check each one, then push them with a lease.

    restack.py [--repo DIR] --onto REF --from REF BRANCH...

The branches are listed bottom to top, as named on the remote. `--from` is the old base of the bottom branch and
`--onto` the new one. Prints one JSON result. Never resolves a conflict, never pushes an unsigned commit, never
uses plain `--force`.
Exit codes: 0 ok, 1 a gate failed, 2 a rebase conflicted, 3 refused or a command failed.
"""

import argparse
import sys
from collections.abc import Mapping
from pathlib import Path

# `gitflow` lives in the code-integrate skill, next to this skill's directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'code-integrate' / 'scripts'))

import gitflow  # noqa: E402 — the import needs the `sys.path` line above
from gitflow import EXIT_GATES_FAILED, EXIT_NEEDS_REBASE, EXIT_OK, EXIT_REFUSED, GitError  # noqa: E402 — same

type Stack = list[dict[str, object]]


def restack(
    repo: Path, onto: str, old: str, branches: list[str], log: Path, gates: Mapping[str, list[str]]
) -> tuple[dict[str, object], int]:
    """Rebase every branch, check each one, and only then push them all, bottom to top.

    Every branch is rebased on a detached HEAD from its `origin/<branch>`, so no local branch moves and nothing is
    pushed until every branch has been rebased, passed the gates and carries only signed commits. A conflict, a
    failed gate or an unsigned commit leaves every branch and the remote as they were.

    Args:
        repo: The repository to work in.
        onto: The ref the bottom branch moves onto.
        old: The ref the bottom branch currently sits on.
        branches: The part branches, bottom to top, as named on the remote.
        log: The file raw git and gate output goes to.
        gates: The command of each gate, by name.

    Returns:
        The result mapping the script prints, and the exit code that goes with it.

    Raises:
        GitError: A git command that must succeed failed.
    """
    gitflow.git(repo, log, 'fetch', 'origin')
    reason = gitflow.require_clean(repo, log)
    if reason:
        return {'status': 'refused', 'reason': reason}, EXIT_REFUSED
    plan = _plan(repo, onto, old, branches, log)
    if isinstance(plan, str):
        return {'status': 'refused', 'reason': plan}, EXIT_REFUSED

    start_branch = gitflow.git(repo, log, 'branch', '--show-current')
    start_sha = gitflow.git(repo, log, 'rev-parse', 'HEAD')
    stack: Stack = []
    try:
        failure = _rebase_and_check(repo, onto, old, plan, log, gates, stack)
        if failure is not None:
            return failure
        # HEAD is detached here, so a local branch the caller had checked out can be moved.
        not_moved = _publish(repo, stack, log)
    except GitError as exc:
        return {'status': 'refused', 'reason': str(exc), 'stack': stack}, EXIT_REFUSED
    finally:
        if start_branch:
            gitflow.git(repo, log, 'switch', start_branch)
        else:
            gitflow.git(repo, log, 'switch', '--detach', start_sha)
    return {'status': 'ok', 'stack': stack, 'local_not_moved': not_moved}, EXIT_OK


def _plan(repo: Path, onto: str, old: str, branches: list[str], log: Path) -> list[tuple[str, str]] | str:
    """Each branch with its remote SHA, bottom to top, or the reason the stack cannot be restacked.

    Args:
        repo: The repository to look in.
        onto: The ref the bottom branch moves onto.
        old: The ref the bottom branch currently sits on.
        branches: The part branches, bottom to top.
        log: The file the commands and their output are appended to.

    Raises:
        GitError: A git command that must succeed failed.
    """
    for ref in (onto, old):
        if gitflow.rev_parse(repo, log, ref) is None:
            return f'{ref} does not exist'
    plan: list[tuple[str, str]] = []
    below = gitflow.git(repo, log, 'rev-parse', f'{old}^{{commit}}')
    for branch in branches:
        remote_sha = gitflow.rev_parse(repo, log, f'origin/{branch}')
        if remote_sha is None:
            return f'origin/{branch} does not exist'
        if not gitflow.is_ancestor(repo, log, below, remote_sha):
            return f'origin/{branch} does not sit on the branch below it'
        local = gitflow.rev_parse(repo, log, f'refs/heads/{branch}')
        if local not in (None, remote_sha) and not gitflow.is_ancestor(repo, log, str(local), remote_sha):
            return f'local {branch} at {local} has commits origin/{branch} does not'
        plan.append((branch, remote_sha))
        below = remote_sha
    return plan


def _rebase_and_check(
    repo: Path,
    onto: str,
    old: str,
    plan: list[tuple[str, str]],
    log: Path,
    gates: Mapping[str, list[str]],
    stack: Stack,
) -> tuple[dict[str, object], int] | None:
    """Rebase each branch on a detached HEAD and check it; None when every branch passed.

    The base of each branch is the tip the branch below it was rebased to, and `--onto` replays only the
    commits after the tip the branch below had before.

    Args:
        repo: The repository to work in.
        onto: The ref the bottom branch moves onto.
        old: The ref the bottom branch currently sits on.
        plan: Each branch with its remote SHA, bottom to top.
        log: The file raw git and gate output goes to.
        gates: The command of each gate, by name.
        stack: Filled with one entry per branch handled, for the result.

    Raises:
        GitError: A git command that must succeed failed.
    """
    new_base = gitflow.git(repo, log, 'rev-parse', f'{onto}^{{commit}}')
    old_base = gitflow.git(repo, log, 'rev-parse', f'{old}^{{commit}}')
    for branch, remote_sha in plan:
        gitflow.git(repo, log, 'switch', '--detach', remote_sha)
        rebased = gitflow.run(repo, log, ['git', 'rebase', '-S', '--onto', new_base, old_base])
        if rebased.returncode != 0:
            gitflow.run(repo, log, ['git', 'rebase', '--abort'])
            return {'status': 'needs_rebase', 'branch': branch, 'stack': stack}, EXIT_NEEDS_REBASE

        new_sha = gitflow.git(repo, log, 'rev-parse', 'HEAD')
        gate_results = gitflow.run_gates(repo, log, gates)
        stack.append({'branch': branch, 'old_sha': remote_sha, 'new_sha': new_sha, 'gates': gate_results})
        if 'fail' in gate_results.values():
            return {'status': 'gates_failed', 'branch': branch, 'stack': stack}, EXIT_GATES_FAILED
        dirty = gitflow.require_clean(repo, log)
        if dirty:
            reason = f'a gate left the tree changed: {dirty}'
            return {'status': 'gates_failed', 'branch': branch, 'reason': reason, 'stack': stack}, EXIT_GATES_FAILED
        unsigned = _unsigned_commits(repo, log, new_base, new_sha)
        if unsigned:
            reason = f'unsigned commits on {branch}: {" ".join(unsigned)}'
            return {'status': 'refused', 'reason': reason, 'branch': branch, 'stack': stack}, EXIT_REFUSED
        new_base, old_base = new_sha, remote_sha
    return None


def _unsigned_commits(repo: Path, log: Path, base: str, tip: str) -> list[str]:
    """The commits between the base and the tip whose `%G?` is not `G`.

    Args:
        repo: The repository to look in.
        log: The file the command and its output are appended to.
        base: The commit the branch sits on.
        tip: The branch's tip.

    Raises:
        GitError: A git command that must succeed failed.
    """
    unsigned: list[str] = []
    for line in gitflow.git(repo, log, 'log', '--format=%H %G?', f'{base}..{tip}').splitlines():
        sha, status = line.split()
        if status != 'G':
            unsigned.append(sha)
    return unsigned


def _publish(repo: Path, stack: Stack, log: Path) -> list[str]:
    """Push every branch in one atomic push, each leased on its old remote SHA, then move the local branches.

    The push is all or nothing, so a rejected lease leaves every remote branch as it was, and the local branches
    move only once the remote has taken the new tips. A local branch that is checked out in another worktree stays
    where it is, since git refuses to move it, and the run is still a success: the remote is what matters.

    Args:
        repo: The repository to work in.
        stack: One entry per branch with its `old_sha` and `new_sha`; `push` is added once the push succeeded.
        log: The file raw git output goes to.

    Returns:
        The branches whose local branch was not moved because another worktree has it checked out.

    Raises:
        GitError: The push was rejected.
    """
    leases = [f'--force-with-lease=refs/heads/{entry["branch"]}:{entry["old_sha"]}' for entry in stack]
    refspecs = [f'{entry["new_sha"]}:refs/heads/{entry["branch"]}' for entry in stack]
    gitflow.git(repo, log, 'push', '--atomic', *leases, 'origin', *refspecs)
    busy = _checked_out_elsewhere(repo, log)
    not_moved: list[str] = []
    for entry in stack:
        branch = str(entry['branch'])
        entry['push'] = 'lease'
        if branch in busy:
            not_moved.append(branch)
        else:
            gitflow.git(repo, log, 'branch', '-f', branch, str(entry['new_sha']))
    return not_moved


def _checked_out_elsewhere(repo: Path, log: Path) -> set[str]:
    """The local branches that a worktree has checked out; this worktree is detached, so it holds none.

    Args:
        repo: The repository to look in.
        log: The file the command and its output are appended to.

    Raises:
        GitError: A git command that must succeed failed.
    """
    prefix = 'branch refs/heads/'
    listed = gitflow.git(repo, log, 'worktree', 'list', '--porcelain').splitlines()
    return {line.removeprefix(prefix) for line in listed if line.startswith(prefix)}


def main(argv: list[str]) -> int:
    """Parse the arguments, restack in the repository and print the result.

    Args:
        argv: The command-line arguments, after the program name.

    Returns:
        The exit code the script ends with.
    """
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        '--repo', type=Path, default=Path(), help='the repository to work in, default the current directory'
    )
    parser.add_argument('--onto', required=True, help='the ref the bottom branch moves onto, such as origin/main')
    parser.add_argument('--from', dest='old', required=True, help='the ref the bottom branch sits on now')
    parser.add_argument('branches', nargs='+', help='the part branches, bottom to top, as named on the remote')
    args = parser.parse_args(argv)

    repo = args.repo.resolve()
    if not gitflow.require_repository(repo):
        return EXIT_REFUSED
    log = gitflow.default_log(repo, 'code-restack')
    try:
        result, code = restack(repo, args.onto, args.old, args.branches, log, gitflow.default_gates())
    except GitError as exc:
        result, code = {'status': 'error', 'reason': str(exc)}, EXIT_REFUSED
    gitflow.emit(result, log)
    return code


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
