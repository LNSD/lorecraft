#!/usr/bin/env python3
"""Integrate a Writer's patches into a part branch, then squash and push it.

    integrate.py apply [--repo DIR] --branch B --base REF PATCH...
    integrate.py squash [--repo DIR] --branch B --base REF --message-file FILE

Prints one JSON result. Never resolves a conflict, never commits unsigned, never uses plain `--force`.
Exit codes: 0 ok, 1 a gate failed, 2 the patches do not apply, 3 refused or a command failed.
"""

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping
from pathlib import Path

import gitflow
from gitflow import EXIT_GATES_FAILED, EXIT_NEEDS_REBASE, EXIT_OK, EXIT_REFUSED, GitError


def apply(
    repo: Path,
    branch: str,
    base: str,
    patches: list[Path],
    log: Path,
    gates: Mapping[str, list[str]],
    *,
    rebase: bool = False,
) -> tuple[dict[str, object], int]:
    """Check out the part branch, apply the patches, run the gates and measure the size.

    A local branch that descends from the remote branch (or from the base, for a new branch) is continued: a
    FIX after a failed gate lands on top of the commits applied before.

    Args:
        repo: The repository to work in.
        branch: The part branch, as named on the remote.
        base: The ref the part sits on.
        patches: The `git format-patch` files, in order.
        log: The file raw git and gate output goes to.
        gates: The command of each gate, by name.
        rebase: Start at `base` and save the fetched remote SHA for `squash`.

    Raises:
        GitError: A git command that must succeed failed.
    """
    gitflow.git(repo, log, 'fetch', 'origin')
    reason = gitflow.require_clean(repo, log)
    if reason:
        return {'status': 'refused', 'reason': reason}, EXIT_REFUSED
    base_sha = gitflow.git(repo, log, 'rev-parse', base)
    expected_remote = gitflow.rev_parse(repo, log, f'origin/{branch}')
    state_path = _rebase_state_path(repo, log, branch)
    # A new apply attempt supersedes any prior lease record, even if this attempt fails.
    state_path.unlink(missing_ok=True)
    start = base_sha if rebase else expected_remote or base_sha
    local = gitflow.rev_parse(repo, log, f'refs/heads/{branch}')
    if local is None or local == start:
        gitflow.git(repo, log, 'switch', '-C', branch, start)
    elif gitflow.is_ancestor(repo, log, start, local):
        gitflow.git(repo, log, 'switch', branch)
    elif rebase:
        gitflow.git(repo, log, 'switch', '-C', branch, start)
    else:
        return {'status': 'refused', 'reason': f'local {branch} at {local} does not descend from {start}'}, EXIT_REFUSED

    applied = gitflow.run(repo, log, ['git', 'am', '--3way', *[str(p.resolve()) for p in patches]])
    if applied.returncode != 0:
        gitflow.run(repo, log, ['git', 'am', '--abort'])
        return {'status': 'needs_rebase', 'branch': branch, 'start_sha': start}, EXIT_NEEDS_REBASE

    gate_results = gitflow.run_gates(repo, log, gates)
    result: dict[str, object] = {
        'status': 'ok',
        'branch': branch,
        'base_sha': base_sha,
        'start_sha': start,
        'head_sha': gitflow.git(repo, log, 'rev-parse', 'HEAD'),
        'commits': int(gitflow.git(repo, log, 'rev-list', '--count', f'{start}..HEAD')),
        'size': gitflow.measure_size(repo, log, base_sha),
        'gates': gate_results,
    }
    if rebase:
        result['lease_sha'] = expected_remote
    if 'fail' in gate_results.values():
        return {**result, 'status': 'gates_failed'}, EXIT_GATES_FAILED
    dirty = gitflow.require_clean(repo, log)
    if dirty:
        return {
            **result,
            'status': 'gates_failed',
            'reason': f'a gate left the tree changed: {dirty}',
        }, EXIT_GATES_FAILED
    if rebase:
        _write_rebase_state(repo, log, branch, base_sha, expected_remote, str(result['head_sha']))
    return result, EXIT_OK


def squash(repo: Path, branch: str, base: str, message_file: Path, log: Path) -> tuple[dict[str, object], int]:
    """Squash the branch into one signed commit on the base and push it.

    In the default mode, reads `origin/<branch>` and refuses when the branch does not contain it. After
    `apply --rebase`, uses the fetched remote SHA and base recorded by that apply, even when the branch does not
    contain the remote SHA.

    Args:
        repo: The repository to work in, with the branch checked out.
        branch: The part branch, as named on the remote.
        base: The ref the part sits on, an ancestor of the branch.
        message_file: The commit message.
        log: The file raw git output goes to.

    Raises:
        GitError: A git command that must succeed failed.
    """
    if gitflow.git(repo, log, 'branch', '--show-current') != branch:
        return {'status': 'refused', 'reason': f'{branch} is not checked out'}, EXIT_REFUSED
    reason = gitflow.require_clean(repo, log)
    if reason:
        return {'status': 'refused', 'reason': reason}, EXIT_REFUSED
    old_head = gitflow.git(repo, log, 'rev-parse', 'HEAD')
    state = _read_rebase_state(repo, log, branch)
    requested_base_sha = gitflow.git(repo, log, 'rev-parse', base)
    if state is not None and state['base_sha'] != requested_base_sha:
        return {'status': 'refused', 'reason': f'{base} changed since apply --rebase'}, EXIT_REFUSED
    base_sha = str(state['base_sha']) if state is not None else requested_base_sha
    if not gitflow.is_ancestor(repo, log, base_sha, old_head):
        return {'status': 'refused', 'reason': f'{base} is not an ancestor of {branch}'}, EXIT_REFUSED
    if state is not None and state['applied_head'] != old_head:
        return {'status': 'refused', 'reason': f'{branch} changed after its successful apply --rebase'}, EXIT_REFUSED
    expected = state['expected_remote'] if state is not None else gitflow.rev_parse(repo, log, f'origin/{branch}')
    if state is None and expected is not None and not gitflow.is_ancestor(repo, log, expected, old_head):
        return {'status': 'refused', 'reason': f'origin/{branch} at {expected} is not in {branch}'}, EXIT_REFUSED

    gitflow.git(repo, log, 'reset', '--soft', base_sha)
    committed = gitflow.run(repo, log, ['git', 'commit', '-s', '-S', '-F', str(message_file.resolve())])
    if committed.returncode != 0:
        reason = 'git commit failed'
        signature = None
    else:
        signature = gitflow.signature_status(repo, log, 'HEAD')
        reason = f'the commit is not signed (%G? = {signature})'
    if signature != 'G':
        # Put the branch back as it was: an unsigned or missing commit is never pushed.
        gitflow.git(repo, log, 'reset', '--soft', old_head)
        return {'status': 'refused', 'reason': reason, 'head_sha': old_head}, EXIT_REFUSED

    try:
        pushed = gitflow.push(repo, log, branch, expected)
    except GitError as error:
        gitflow.git(repo, log, 'reset', '--soft', old_head)
        return {'status': 'refused', 'reason': str(error), 'head_sha': old_head}, EXIT_REFUSED
    if state is not None:
        _rebase_state_path(repo, log, branch).unlink(missing_ok=True)
    return {
        'status': 'ok',
        'branch': branch,
        'base_sha': base_sha,
        'head_sha': gitflow.git(repo, log, 'rev-parse', 'HEAD'),
        'signature': signature,
        'push': pushed,
    }, EXIT_OK


def main(argv: list[str]) -> int:
    """Parse the arguments, run the subcommand in the repository and print its result.

    Args:
        argv: The command-line arguments, after the program name.
    """
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('apply', 'squash'):
        sub = commands.add_parser(name)
        sub.add_argument(
            '--repo', type=Path, default=Path(), help='the repository to work in, default the current directory'
        )
        sub.add_argument('--branch', required=True, help='the part branch, as named on the remote')
        sub.add_argument('--base', required=True, help='the ref the part sits on, such as origin/main')
        if name == 'apply':
            sub.add_argument(
                '--rebase', action='store_true', help='start at --base and pin squash to origin/<branch> fetched now'
            )
            sub.add_argument('patches', nargs='+', type=Path)
        else:
            sub.add_argument('--message-file', required=True, type=Path)
    args = parser.parse_args(argv)

    # Patch and message-file paths stay relative to the caller's directory, not to `--repo`.
    repo = args.repo.resolve()
    if not gitflow.require_repository(repo):
        return EXIT_REFUSED
    log = gitflow.default_log(repo, f'code-integrate-{args.command}')
    try:
        if args.command == 'apply':
            result, code = apply(
                repo, args.branch, args.base, args.patches, log, gitflow.default_gates(), rebase=args.rebase
            )
        else:
            result, code = squash(repo, args.branch, args.base, args.message_file, log)
    except GitError as error:
        result, code = {'status': 'error', 'reason': str(error)}, EXIT_REFUSED
    gitflow.emit(result, log)
    return code


def _rebase_state_path(repo: Path, log: Path, branch: str) -> Path:
    """The git-directory file holding the remote lease and head from a successful rebased apply."""
    git_dir = Path(gitflow.git(repo, log, 'rev-parse', '--absolute-git-dir'))
    branch_id = hashlib.sha256(branch.encode()).hexdigest()
    return git_dir / f'code-integrate-rebase-{branch_id}.json'


def _write_rebase_state(
    repo: Path, log: Path, branch: str, base_sha: str, expected_remote: str | None, applied_head: str
) -> None:
    """Record the fetched remote lease and clean applied head for `squash`."""
    path = _rebase_state_path(repo, log, branch)
    state = {
        'branch': branch,
        'base_sha': base_sha,
        'expected_remote': expected_remote,
        'applied_head': applied_head,
    }
    try:
        path.write_text(json.dumps(state), encoding='utf-8')
    except OSError as error:
        raise GitError(f'could not write rebase apply state: {error}') from error


def _read_rebase_state(repo: Path, log: Path, branch: str) -> dict[str, str | None] | None:
    """Read a matching successful rebase apply state, or None for the default integration flow."""
    path = _rebase_state_path(repo, log, branch)
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as error:
        raise GitError(f'could not read rebase apply state: {error}') from error
    if (
        not isinstance(value, dict)
        or value.get('branch') != branch
        or not isinstance(value.get('base_sha'), str)
        or not isinstance(value.get('applied_head'), str)
        or (value.get('expected_remote') is not None and not isinstance(value.get('expected_remote'), str))
    ):
        raise GitError(f'invalid rebase apply state for {branch}')
    return value


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
