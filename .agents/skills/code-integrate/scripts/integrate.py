#!/usr/bin/env python3
"""Integrate a Writer's patches into a part branch.

    integrate.py apply --branch B --base REF PATCH...

Prints one JSON result. Never resolves a conflict. Exit codes: 0 ok, 1 a gate failed, 2 the patches do not apply,
3 refused or a command failed.
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


def main(argv: list[str]) -> int:
    """Parse the arguments, run the subcommand in the current directory and print its result.

    Args:
        argv: The command-line arguments, after the program name.
    """
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest='command', required=True)
    apply_parser = commands.add_parser('apply')
    apply_parser.add_argument('--branch', required=True, help='the part branch, as named on the remote')
    apply_parser.add_argument('--base', required=True, help='the ref the part sits on, such as origin/main')
    apply_parser.add_argument('patches', nargs='+', type=Path)
    args = parser.parse_args(argv)

    repo = Path.cwd()
    log = gitflow.default_log(repo, f'code-integrate-{args.command}')
    try:
        result, code = apply(repo, args.branch, args.base, args.patches, log, gitflow.default_gates())
    except GitError as error:
        result, code = {'status': 'error', 'reason': str(error)}, EXIT_REFUSED
    gitflow.emit(result, log)
    return code


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
