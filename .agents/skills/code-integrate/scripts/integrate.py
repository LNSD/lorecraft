#!/usr/bin/env python3
"""Integrate a Writer's patches into a part branch, then squash and push it.

    integrate.py apply --branch B --base REF PATCH...
    integrate.py squash --branch B --base REF --message-file FILE

Prints one JSON result. Never resolves a conflict, never commits unsigned, never uses plain `--force`.
Exit codes: 0 ok, 1 a gate failed, 2 the patches do not apply, 3 refused or a command failed.
"""

import argparse
import sys
from collections.abc import Mapping
from pathlib import Path

import gitflow
from gitflow import EXIT_GATES_FAILED, EXIT_NEEDS_REBASE, EXIT_OK, EXIT_REFUSED, GitError


def apply(
    repo: Path, branch: str, base: str, patches: list[Path], log: Path, gates: Mapping[str, list[str]]
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

    Raises:
        GitError: A git command that must succeed failed.
    """
    gitflow.git(repo, log, 'fetch', 'origin')
    reason = gitflow.require_clean(repo, log)
    if reason:
        return {'status': 'refused', 'reason': reason}, EXIT_REFUSED
    base_sha = gitflow.git(repo, log, 'rev-parse', base)
    start = gitflow.rev_parse(repo, log, f'origin/{branch}') or base_sha
    local = gitflow.rev_parse(repo, log, f'refs/heads/{branch}')
    if local is None or local == start:
        gitflow.git(repo, log, 'switch', '-C', branch, start)
    elif gitflow.is_ancestor(repo, log, start, local):
        gitflow.git(repo, log, 'switch', branch)
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
    if 'fail' in gate_results.values():
        return {**result, 'status': 'gates_failed'}, EXIT_GATES_FAILED
    dirty = gitflow.require_clean(repo, log)
    if dirty:
        return {
            **result,
            'status': 'gates_failed',
            'reason': f'a gate left the tree changed: {dirty}',
        }, EXIT_GATES_FAILED
    return result, EXIT_OK


def squash(repo: Path, branch: str, base: str, message_file: Path, log: Path) -> tuple[dict[str, object], int]:
    """Squash the branch into one signed commit on the base and push it.

    Reads `origin/<branch>` as the last `apply` fetched it, and refuses when the branch does not contain it.

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
    base_sha = gitflow.git(repo, log, 'rev-parse', base)
    old_head = gitflow.git(repo, log, 'rev-parse', 'HEAD')
    if not gitflow.is_ancestor(repo, log, base_sha, old_head):
        return {'status': 'refused', 'reason': f'{base} is not an ancestor of {branch}'}, EXIT_REFUSED
    expected = gitflow.rev_parse(repo, log, f'origin/{branch}')
    if expected is not None and not gitflow.is_ancestor(repo, log, expected, old_head):
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
    return {
        'status': 'ok',
        'branch': branch,
        'base_sha': base_sha,
        'head_sha': gitflow.git(repo, log, 'rev-parse', 'HEAD'),
        'signature': signature,
        'push': pushed,
    }, EXIT_OK


def main(argv: list[str]) -> int:
    """Parse the arguments, run the subcommand in the current directory and print its result.

    Args:
        argv: The command-line arguments, after the program name.
    """
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('apply', 'squash'):
        sub = commands.add_parser(name)
        sub.add_argument('--branch', required=True, help='the part branch, as named on the remote')
        sub.add_argument('--base', required=True, help='the ref the part sits on, such as origin/main')
        if name == 'apply':
            sub.add_argument('patches', nargs='+', type=Path)
        else:
            sub.add_argument('--message-file', required=True, type=Path)
    args = parser.parse_args(argv)

    repo = Path.cwd()
    log = gitflow.default_log(repo, f'code-integrate-{args.command}')
    try:
        if args.command == 'apply':
            result, code = apply(repo, args.branch, args.base, args.patches, log, gitflow.default_gates())
        else:
            result, code = squash(repo, args.branch, args.base, args.message_file, log)
    except GitError as error:
        result, code = {'status': 'error', 'reason': str(error)}, EXIT_REFUSED
    gitflow.emit(result, log)
    return code


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
