"""The code-integrate and code-sync scripts work in the repository `--repo` names, not in the working directory."""

import importlib
import json
import subprocess
import sys
from pathlib import Path
from textwrap import dedent
from types import ModuleType

import pytest

SKILLS = Path(__file__).resolve().parents[2] / '.agents' / 'skills'
INTEGRATE = SKILLS / 'code-integrate' / 'scripts' / 'integrate.py'
SYNC = SKILLS / 'code-sync' / 'scripts' / 'sync.py'
RESTACK = SKILLS / 'code-restack' / 'scripts' / 'restack.py'
EXIT_GATES_FAILED = 1
EXIT_REFUSED = 3


def _rebase_case(tmp_path: Path) -> tuple[Path, Path, str, str]:
    """Build a bare-remote repo, a newer base, and one Writer patch for integration tests."""
    repo = _init_repo(tmp_path / 'repo')
    _git(repo, 'switch', '-c', 'lnsd/x')
    (repo / 'remote.txt').write_text('remote\n')
    _git(repo, 'add', 'remote.txt')
    _git(repo, 'commit', '-m', 'remote branch')
    _git(repo, 'push', '-u', 'origin', 'lnsd/x')
    remote_sha = _git(repo, 'rev-parse', 'HEAD')
    _git(repo, 'switch', 'main')
    (repo / 'base.txt').write_text('base\n')
    justfile = dedent("""\
        fmt-check:
            @true
        check:
            @true
        typecheck:
            @true
        test:
            @true
        check-docs:
            @true
        """)
    (repo / 'justfile').write_text(justfile, encoding='utf-8')
    _git(repo, 'add', 'base.txt', 'justfile')
    _git(repo, 'commit', '-m', 'new base')
    _git(repo, 'push', 'origin', 'main')
    base_sha = _git(repo, 'rev-parse', 'HEAD')
    _git(repo, 'switch', '-c', 'writer')
    (repo / 'writer.txt').write_text('writer\n')
    _git(repo, 'add', 'writer.txt')
    _git(repo, 'commit', '-m', 'writer change')
    patches = tmp_path / 'patches'
    patches.mkdir()
    patch = Path(_git(repo, 'format-patch', '-1', '-o', str(patches)))
    _git(repo, 'switch', 'main')
    return repo, patch, remote_sha, base_sha


def _apply_rebase(repo: Path, patch: Path, tmp_path: Path) -> tuple[dict[str, object], int]:
    return _script(
        INTEGRATE,
        tmp_path,
        'apply',
        '--repo',
        str(repo),
        '--branch',
        'lnsd/x',
        '--base',
        'origin/main',
        '--rebase',
        str(patch),
    )


def _load_integrate(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    monkeypatch.syspath_prepend(str(INTEGRATE.parent))
    return importlib.import_module('integrate')


def _squash_inputs(repo: Path, tmp_path: Path) -> tuple[Path, Path]:
    message = tmp_path / 'message.txt'
    message.write_text('refactor: test squash\n', encoding='utf-8')
    log = repo / '.git' / 'squash.log'
    log.write_text('', encoding='utf-8')
    return message, log


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

        arguments = [
            'apply',
            '--repo',
            str(repo),
            '--branch',
            'lnsd/x',
            '--base',
            'origin/main',
            'patches/0001-feat-add-b.patch',
        ]

        #: When
        result, code = _script(INTEGRATE, caller, *arguments)

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

        arguments = [
            'squash',
            '--repo',
            str(repo),
            '--branch',
            'lnsd/x',
            '--base',
            'origin/main',
            '--message-file',
            'message.txt',
        ]

        #: When
        result, code = _script(INTEGRATE, elsewhere, *arguments)

        #: Then
        assert code == EXIT_REFUSED, 'the branch checked out in --repo is not the part branch'
        assert result['reason'] == 'lnsd/x is not checked out', 'the branch of the working directory is not consulted'

    def test_sync_refuses_the_dirty_repo_not_the_clean_working_directory(self, tmp_path: Path) -> None:
        #: Given
        repo = _init_repo(tmp_path / 'repo')
        (repo / 'a.txt').write_text('dirty\n')
        clean = _init_repo(tmp_path / 'clean')

        arguments = ['--repo', str(repo), '1']

        #: When
        result, code = _script(SYNC, clean, *arguments)

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


@pytest.mark.e2e
class TestCodeIntegrateRebaseMode:
    def test_default_apply_continues_from_the_remote_branch(self, tmp_path: Path) -> None:
        #: Given
        repo, patch, remote_sha, _base_sha = _rebase_case(tmp_path)
        _git(repo, 'push', 'origin', f'{remote_sha}:refs/heads/lnsd/default')
        arguments = ['apply', '--repo', str(repo), '--branch', 'lnsd/default', '--base', 'origin/main', str(patch)]

        #: When
        result, code = _script(INTEGRATE, tmp_path, *arguments)

        #: Then
        assert code == EXIT_GATES_FAILED, result
        assert result['start_sha'] == remote_sha, 'default apply still starts at the remote part branch'
        assert (repo / 'remote.txt').exists(), 'default apply retains the remote branch content'
        assert not (repo / 'base.txt').exists(), 'default apply does not move an existing part branch to the base'

    def test_rebase_apply_starts_at_base_and_records_the_fetched_lease(self, tmp_path: Path) -> None:
        #: Given
        repo, patch, remote_sha, base_sha = _rebase_case(tmp_path)

        #: When
        result, code = _apply_rebase(repo, patch, tmp_path)

        #: Then
        assert code == 0, result
        assert result['start_sha'] == base_sha, 'the rebased patch series starts at the requested base'
        assert result['lease_sha'] == remote_sha, 'the apply records the remote head it fetched'
        assert _git(repo, 'merge-base', '--is-ancestor', base_sha, 'HEAD') == '', 'the branch descends from the base'
        assert (repo / 'base.txt').read_text(encoding='utf-8') == 'base\n', 'the base content is retained'
        assert (repo / 'writer.txt').read_text(encoding='utf-8') == 'writer\n', 'the writer patch is applied'
        assert not (repo / 'remote.txt').exists(), 'the old remote branch content is not part of the rebase'

    def test_squash_refuses_a_dirty_rebased_branch(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        #: Given
        repo, patch, _remote_sha, _base_sha = _rebase_case(tmp_path)
        applied, apply_code = _apply_rebase(repo, patch, tmp_path)
        assert apply_code == 0, applied
        integrate = _load_integrate(monkeypatch)
        message, log = _squash_inputs(repo, tmp_path)
        (repo / 'dirty.txt').write_text('dirty\n')

        #: When
        result, code = integrate.squash(repo, 'lnsd/x', 'origin/main', message, log)

        #: Then
        assert code == EXIT_REFUSED, result
        assert result['reason'] == 'the working tree is not clean', 'squash still refuses a dirty tree'

    def test_squash_refuses_an_unsigned_rebased_commit(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        #: Given
        repo, patch, _remote_sha, _base_sha = _rebase_case(tmp_path)
        applied, apply_code = _apply_rebase(repo, patch, tmp_path)
        assert apply_code == 0, applied
        integrate = _load_integrate(monkeypatch)
        message, log = _squash_inputs(repo, tmp_path)
        run = integrate.gitflow.run

        def commit_without_gpg(repo_path: Path, log_path: Path, command: list[str]) -> subprocess.CompletedProcess[str]:
            if command[:2] == ['git', 'commit'] and '-S' in command:
                command = [argument for argument in command if argument != '-S']
            return run(repo_path, log_path, command)

        monkeypatch.setattr(integrate.gitflow, 'run', commit_without_gpg)
        monkeypatch.setattr(integrate.gitflow, 'signature_status', lambda _repo, _log, _rev: 'N')

        #: When
        result, code = integrate.squash(repo, 'lnsd/x', 'origin/main', message, log)

        #: Then
        assert code == EXIT_REFUSED, result
        assert 'not signed' in str(result['reason']), 'squash still refuses an unsigned commit'
        assert 'git push' not in log.read_text(encoding='utf-8'), 'an unsigned commit is never pushed'

    def test_successful_squash_clears_rebase_state_for_a_later_reword(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        #: Given
        repo, patch, _remote_sha, _base_sha = _rebase_case(tmp_path)
        applied, apply_code = _apply_rebase(repo, patch, tmp_path)
        assert apply_code == 0, applied
        integrate = _load_integrate(monkeypatch)
        run = integrate.gitflow.run

        def commit_without_gpg(repo_path: Path, log_path: Path, command: list[str]) -> subprocess.CompletedProcess[str]:
            if command[:2] == ['git', 'commit'] and '-S' in command:
                command = [argument for argument in command if argument != '-S']
            return run(repo_path, log_path, command)

        monkeypatch.setattr(integrate.gitflow, 'run', commit_without_gpg)
        monkeypatch.setattr(integrate.gitflow, 'signature_status', lambda _repo, _log, _rev: 'G')
        message, log = _squash_inputs(repo, tmp_path)
        state_path = integrate._rebase_state_path(repo, log, 'lnsd/x')

        #: When
        result, code = integrate.squash(repo, 'lnsd/x', 'origin/main', message, log)

        #: Then
        assert code == 0, result
        assert not state_path.exists(), 'a pushed squash no longer leaves its apply record behind'

    def test_squash_rejects_a_concurrent_remote_update_with_the_fetched_lease(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        #: Given
        repo, patch, remote_sha, _base_sha = _rebase_case(tmp_path)
        applied, apply_code = _apply_rebase(repo, patch, tmp_path)
        assert apply_code == 0, applied
        _git(repo, 'switch', '-c', 'concurrent', 'origin/lnsd/x')
        (repo / 'concurrent.txt').write_text('concurrent\n')
        _git(repo, 'add', 'concurrent.txt')
        _git(repo, 'commit', '-m', 'concurrent remote update')
        _git(repo, 'push', 'origin', 'HEAD:refs/heads/lnsd/x')
        concurrent_sha = _git(repo, 'rev-parse', 'HEAD')
        _git(repo, 'fetch', 'origin')
        _git(repo, 'switch', 'lnsd/x')
        integrate = _load_integrate(monkeypatch)
        run = integrate.gitflow.run

        def commit_without_gpg(repo_path: Path, log_path: Path, command: list[str]) -> subprocess.CompletedProcess[str]:
            if command[:2] == ['git', 'commit'] and '-S' in command:
                command = [argument for argument in command if argument != '-S']
            return run(repo_path, log_path, command)

        monkeypatch.setattr(integrate.gitflow, 'run', commit_without_gpg)
        monkeypatch.setattr(integrate.gitflow, 'signature_status', lambda _repo, _log, _rev: 'G')
        message, log = _squash_inputs(repo, tmp_path)

        #: When
        result, code = integrate.squash(repo, 'lnsd/x', 'origin/main', message, log)

        #: Then
        assert code == EXIT_REFUSED, result
        assert 'push' in str(result['reason']), 'the stale lease reaches the remote push and is rejected'
        assert _git(repo, 'ls-remote', 'origin', 'refs/heads/lnsd/x').split()[0] == concurrent_sha, (
            'a concurrent remote update is left intact'
        )
        assert f'--force-with-lease=refs/heads/lnsd/x:{remote_sha}' in log.read_text(encoding='utf-8'), (
            'squash pins the lease to the SHA fetched by apply'
        )
