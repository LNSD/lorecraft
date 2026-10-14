"""The code-integrate and code-sync scripts work in the repository `--repo` names, not in the working directory."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

SKILLS = Path(__file__).resolve().parents[2] / '.agents' / 'skills'
INTEGRATE = SKILLS / 'code-integrate' / 'scripts' / 'integrate.py'
SYNC = SKILLS / 'code-sync' / 'scripts' / 'sync.py'
RESTACK = SKILLS / 'code-restack' / 'scripts' / 'restack.py'
EXIT_GATES_FAILED = 1
EXIT_REFUSED = 3


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(['git', *args], cwd=repo, capture_output=True, text=True, check=True)
    return done.stdout.strip()


def _init_repo(path: Path) -> Path:
    """A repository with one commit on `main` and a bare `origin`."""
    origin = path.parent / f'{path.name}-origin.git'
    subprocess.run(['git', 'init', '--bare', '-b', 'main', str(origin)], check=True, capture_output=True)
    path.mkdir()
    _git(path, 'init', '-b', 'main')
    _git(path, 'config', 'user.name', 'Test')
    _git(path, 'config', 'user.email', 'test@example.com')
    _git(path, 'config', 'commit.gpgsign', 'false')
    (path / 'a.txt').write_text('a\n')
    _git(path, 'add', 'a.txt')
    _git(path, 'commit', '-m', 'init')
    _git(path, 'remote', 'add', 'origin', str(origin))
    _git(path, 'push', 'origin', 'main')
    return path


def _script(script: Path, cwd: Path, *args: str) -> tuple[dict[str, object], int]:
    done = subprocess.run([sys.executable, str(script), *args], cwd=cwd, capture_output=True, text=True, check=False)
    return json.loads(done.stdout.strip().splitlines()[-1]), done.returncode


def _refusal_for_plain_directory(tmp_path: Path, script: Path, args: list[str]) -> tuple[dict[str, object], int, Path]:
    """Run the script with `--repo` naming a directory that holds no git repository."""
    plain = tmp_path / 'plain'
    plain.mkdir()
    result, code = _script(script, tmp_path, *args, '--repo', str(plain))
    return result, code, plain


def _refusal_for_missing_directory(
    tmp_path: Path, script: Path, args: list[str]
) -> tuple[dict[str, object], int, Path]:
    """Run the script with `--repo` naming a path that does not exist."""
    missing = tmp_path / 'missing'
    result, code = _script(script, tmp_path, *args, '--repo', str(missing))
    return result, code, missing


@pytest.mark.e2e
class TestScriptsTakeTheRepositoryFromRepo:
    def test_apply_applies_a_patch_given_relative_to_the_callers_directory_onto_the_repo(self, tmp_path: Path) -> None:
        #: Given
        repo = _init_repo(tmp_path / 'repo')
        _git(repo, 'switch', '-c', 'writer')
        (repo / 'b.txt').write_text('b\n')
        _git(repo, 'add', 'b.txt')
        _git(repo, 'commit', '-m', 'feat: add b')
        caller = tmp_path / 'caller'
        caller.mkdir()
        _git(repo, 'format-patch', '-1', '-o', str(caller / 'patches'))
        _git(repo, 'switch', 'main')

        #: When
        result, code = _script(
            INTEGRATE,
            caller,
            'apply',
            '--repo',
            str(repo),
            '--branch',
            'lnsd/x',
            '--base',
            'origin/main',
            'patches/0001-feat-add-b.patch',
        )

        #: Then
        # No `justfile` in the repository, so the first gate fails after the patch was applied.
        assert code == EXIT_GATES_FAILED, 'the first gate fails once the patch is applied'
        assert result['branch'] == 'lnsd/x', 'the result names the part branch'
        assert result['commits'] == 1, 'the patch given relative to the caller was applied in --repo'
        assert _git(repo, 'branch', '--show-current') == 'lnsd/x', 'the part branch is checked out in --repo'

    def test_squash_judges_the_branch_checked_out_in_the_repo_not_in_the_working_directory(
        self, tmp_path: Path
    ) -> None:
        #: Given
        repo = _init_repo(tmp_path / 'repo')
        elsewhere = _init_repo(tmp_path / 'elsewhere')
        _git(elsewhere, 'switch', '-c', 'lnsd/x')

        #: When
        result, code = _script(
            INTEGRATE,
            elsewhere,
            'squash',
            '--repo',
            str(repo),
            '--branch',
            'lnsd/x',
            '--base',
            'origin/main',
            '--message-file',
            'message.txt',
        )

        #: Then
        assert code == EXIT_REFUSED, 'the branch checked out in --repo is not the part branch'
        assert result['reason'] == 'lnsd/x is not checked out', 'the branch of the working directory is not consulted'

    def test_sync_refuses_the_dirty_repo_not_the_clean_working_directory(self, tmp_path: Path) -> None:
        #: Given
        repo = _init_repo(tmp_path / 'repo')
        (repo / 'a.txt').write_text('dirty\n')
        clean = _init_repo(tmp_path / 'clean')

        #: When
        result, code = _script(SYNC, clean, '--repo', str(repo), '1')

        #: Then
        assert code == EXIT_REFUSED, 'the dirty tree of --repo is refused'
        assert result['reason'] == 'the working tree is not clean', 'the clean working directory is not consulted'

    def test_apply_refuses_a_directory_that_is_not_a_git_repository(self, tmp_path: Path) -> None:
        #: When
        result, code, repo = _refusal_for_plain_directory(
            tmp_path, INTEGRATE, ['apply', '--branch', 'b', '--base', 'origin/main', 'x.patch']
        )

        #: Then
        assert code == EXIT_REFUSED, 'a bad --repo is refused, not a traceback'
        assert result == {'status': 'refused', 'reason': f'{repo} is not a git repository'}, 'the result names the path'

    def test_apply_refuses_a_missing_directory(self, tmp_path: Path) -> None:
        #: When
        result, code, repo = _refusal_for_missing_directory(
            tmp_path, INTEGRATE, ['apply', '--branch', 'b', '--base', 'origin/main', 'x.patch']
        )

        #: Then
        assert code == EXIT_REFUSED, 'a bad --repo is refused, not a traceback'
        assert result == {'status': 'refused', 'reason': f'{repo} is not a git repository'}, 'the result names the path'

    def test_squash_refuses_a_directory_that_is_not_a_git_repository(self, tmp_path: Path) -> None:
        #: When
        result, code, repo = _refusal_for_plain_directory(
            tmp_path, INTEGRATE, ['squash', '--branch', 'b', '--base', 'origin/main', '--message-file', 'm.txt']
        )

        #: Then
        assert code == EXIT_REFUSED, 'a bad --repo is refused, not a traceback'
        assert result == {'status': 'refused', 'reason': f'{repo} is not a git repository'}, 'the result names the path'

    def test_squash_refuses_a_missing_directory(self, tmp_path: Path) -> None:
        #: When
        result, code, repo = _refusal_for_missing_directory(
            tmp_path, INTEGRATE, ['squash', '--branch', 'b', '--base', 'origin/main', '--message-file', 'm.txt']
        )

        #: Then
        assert code == EXIT_REFUSED, 'a bad --repo is refused, not a traceback'
        assert result == {'status': 'refused', 'reason': f'{repo} is not a git repository'}, 'the result names the path'

    def test_sync_refuses_a_directory_that_is_not_a_git_repository(self, tmp_path: Path) -> None:
        #: When
        result, code, repo = _refusal_for_plain_directory(tmp_path, SYNC, ['1'])

        #: Then
        assert code == EXIT_REFUSED, 'a bad --repo is refused, not a traceback'
        assert result == {'status': 'refused', 'reason': f'{repo} is not a git repository'}, 'the result names the path'

    def test_sync_refuses_a_missing_directory(self, tmp_path: Path) -> None:
        #: When
        result, code, repo = _refusal_for_missing_directory(tmp_path, SYNC, ['1'])

        #: Then
        assert code == EXIT_REFUSED, 'a bad --repo is refused, not a traceback'
        assert result == {'status': 'refused', 'reason': f'{repo} is not a git repository'}, 'the result names the path'

    def test_restack_refuses_a_directory_that_is_not_a_git_repository(self, tmp_path: Path) -> None:
        #: When
        result, code, repo = _refusal_for_plain_directory(
            tmp_path, RESTACK, ['--onto', 'origin/main', '--from', 'origin/main', 'b']
        )

        #: Then
        assert code == EXIT_REFUSED, 'a bad --repo is refused, not a traceback'
        assert result == {'status': 'refused', 'reason': f'{repo} is not a git repository'}, 'the result names the path'

    def test_restack_refuses_a_missing_directory(self, tmp_path: Path) -> None:
        #: When
        result, code, repo = _refusal_for_missing_directory(
            tmp_path, RESTACK, ['--onto', 'origin/main', '--from', 'origin/main', 'b']
        )

        #: Then
        assert code == EXIT_REFUSED, 'a bad --repo is refused, not a traceback'
        assert result == {'status': 'refused', 'reason': f'{repo} is not a git repository'}, 'the result names the path'
