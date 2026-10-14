#!/usr/bin/env python3
"""Helpers shared by the code-integrate, code-restack and code-sync scripts.

Plain standard library, readable top to bottom. Raw git and gate output goes to a log file, and a script prints
one compact JSON result, so the agent that runs it reads a few lines instead of the output.

This module lives in `code-integrate/scripts/`. A script of another skill imports it by putting that directory on
`sys.path` before `import gitflow`: `Path(__file__).resolve().parents[2] / 'code-integrate' / 'scripts'`. Moving
or renaming `code-integrate` breaks those skills, so each of them names this module in its `compatibility` line.
"""

import json
import subprocess
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Final

# `fmt-check`, not `fmt`: a gate only reports, so it never rewrites the tree it is judging.
GATES: Final[tuple[str, ...]] = ('fmt-check', 'check', 'typecheck', 'test', 'check-docs')
LOCKFILES: Final[tuple[str, ...]] = (
    'uv.lock',
    'Cargo.lock',
    'poetry.lock',
    'package-lock.json',
    'pnpm-lock.yaml',
    'yarn.lock',
)

# Exit codes shared by every script; the SKILL.md of each one documents them.
EXIT_OK: Final[int] = 0
EXIT_GATES_FAILED: Final[int] = 1
EXIT_NEEDS_REBASE: Final[int] = 2
EXIT_REFUSED: Final[int] = 3


class GitError(Exception):
    """A git command that must succeed did not; the message names the command."""


def default_gates() -> Mapping[str, list[str]]:
    """The gates, by name, each with the command that runs it."""
    return MappingProxyType({gate: ['just', gate] for gate in GATES})


def run(repo: Path, log: Path, command: list[str]) -> subprocess.CompletedProcess[str]:
    """Run a command in the repository and append the command and its whole output to the log.

    Args:
        repo: The directory the command runs in.
        log: The file the command and its output are appended to.
        command: The program and its arguments.
    """
    done = subprocess.run(command, cwd=repo, capture_output=True, text=True, check=False)
    with log.open('a') as file:
        file.write(f'$ {" ".join(command)}\n{done.stdout}{done.stderr}[exit {done.returncode}]\n')
    return done


def git(repo: Path, log: Path, *args: str) -> str:
    """Run a git command that must succeed and return its stripped output.

    Args:
        repo: The repository the command runs in.
        log: The file the command and its output are appended to.
        args: The git arguments, after `git`.

    Raises:
        GitError: The command exited non-zero.
    """
    done = run(repo, log, ['git', *args])
    if done.returncode != 0:
        raise GitError(f'git {" ".join(args)} failed: {done.stderr.strip()}')
    return done.stdout.strip()


def rev_parse(repo: Path, log: Path, ref: str) -> str | None:
    """The commit a ref names, or None when the ref does not exist.

    Args:
        repo: The repository to look in.
        log: The file the command and its output are appended to.
        ref: The ref to resolve.
    """
    done = run(repo, log, ['git', 'rev-parse', '--verify', '--quiet', f'{ref}^{{commit}}'])
    return done.stdout.strip() if done.returncode == 0 else None


def is_ancestor(repo: Path, log: Path, ancestor: str, descendant: str) -> bool:
    """Whether the first commit is reachable from the second, a commit being its own ancestor.

    Args:
        repo: The repository to look in.
        log: The file the command and its output are appended to.
        ancestor: The commit that should be reachable.
        descendant: The commit it is reached from.
    """
    return run(repo, log, ['git', 'merge-base', '--is-ancestor', ancestor, descendant]).returncode == 0


def require_clean(repo: Path, log: Path) -> str | None:
    """None when the working tree and index are clean, otherwise the reason a script refuses to go on.

    Args:
        repo: The repository to look in.
        log: The file the command and its output are appended to.
    """
    if git(repo, log, 'status', '--porcelain'):
        return 'the working tree is not clean'
    return None


def default_log(repo: Path, name: str) -> Path:
    """A fresh log file inside the git directory, which no commit can pick up.

    Args:
        repo: The repository whose git directory holds the log.
        name: The log's file name, without extension.
    """
    git_dir = Path(subprocess.check_output(['git', 'rev-parse', '--absolute-git-dir'], cwd=repo, text=True).strip())
    log = git_dir / f'{name}.log'
    log.write_text('')
    return log


def run_gates(repo: Path, log: Path, gates: Mapping[str, list[str]]) -> dict[str, str]:
    """Run the gates in order and stop at the first failure; a gate that did not run is absent.

    Args:
        repo: The repository the gates run in.
        log: The file the gates' output is appended to.
        gates: The command of each gate, by name.
    """
    results: dict[str, str] = {}
    for name, command in gates.items():
        passed = run(repo, log, command).returncode == 0
        results[name] = 'pass' if passed else 'fail'
        if not passed:
            break
    return results


def measure_size(repo: Path, log: Path, base: str) -> int:
    """Lines added plus deleted between the base and HEAD, lockfiles and binary files excluded.

    Args:
        repo: The repository to measure in.
        log: The file the command and its output are appended to.
        base: The commit the change is measured against.
    """
    total = 0
    for line in git(repo, log, 'diff', '--numstat', base, 'HEAD').splitlines():
        added, deleted, path = line.split('\t', 2)
        if Path(path).name in LOCKFILES or added == '-':
            continue
        total += int(added) + int(deleted)
    return total


def signature_status(repo: Path, log: Path, rev: str) -> str:
    """The `%G?` code of a commit; `G` is a good signature.

    Args:
        repo: The repository to look in.
        log: The file the command and its output are appended to.
        rev: The commit to read.
    """
    return git(repo, log, 'log', '-1', '--format=%G?', rev)


def push(repo: Path, log: Path, branch: str, expected: str | None) -> str:
    """Push a branch with `-u` and a lease pinned to the remote SHA the caller last fetched.

    The push fails when the remote branch is no longer at `expected`, so work pushed since the caller's fetch is
    never overwritten. Plain `--force` is never used.

    Args:
        repo: The repository to push from.
        log: The file the command and its output are appended to.
        branch: The branch, named the same locally and on the remote.
        expected: The commit `origin/<branch>` was at when the caller fetched, or None when the branch is new.

    Raises:
        GitError: The push was rejected.
    """
    # An empty expected value tells git the remote branch must not exist yet.
    lease = f'--force-with-lease=refs/heads/{branch}:{expected or ""}'
    git(repo, log, 'push', '-u', lease, 'origin', f'{branch}:refs/heads/{branch}')
    return 'new' if expected is None else 'lease'


def emit(result: Mapping[str, object], log: Path) -> None:
    """Print the one compact JSON result a script ends with, naming the log.

    Args:
        result: What the script found and what the caller does next.
        log: The log file the result names.
    """
    print(json.dumps({**result, 'log': str(log)}, separators=(',', ':')))
