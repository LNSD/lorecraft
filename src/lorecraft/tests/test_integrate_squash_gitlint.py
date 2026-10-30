"""Unit tests for the message validation boundary in code-integrate's squash."""

import importlib
import subprocess
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / '.agents' / 'skills' / 'code-integrate' / 'scripts' / 'integrate.py'


def _load_integrate(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """Import the workspace script and its adjacent shared helpers."""
    monkeypatch.syspath_prepend(str(SCRIPT.parent))
    return importlib.import_module('integrate')


@pytest.mark.unit
class TestSquashGitlint:
    def test_invalid_message_refuses_before_reset_and_push(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        #: Given
        integrate = _load_integrate(monkeypatch)
        repo = tmp_path / 'repo'
        repo.mkdir()
        message = tmp_path / 'message.txt'
        message.write_text('invalid message\n', encoding='utf-8')
        log = tmp_path / 'log'
        log.write_text('', encoding='utf-8')
        commands: list[list[str]] = []

        def git(_repo: Path, _log: Path, *args: str) -> str:
            if args == ('rev-parse', '--absolute-git-dir'):
                return str(tmp_path / 'git')
            return {
                'branch --show-current': 'lnsd/x',
                'rev-parse HEAD': 'head-sha',
                'rev-parse origin/main': 'base-sha',
            }[' '.join(args)]

        def run(
            command: list[str], *, cwd: Path, capture_output: bool, text: bool, check: bool
        ) -> subprocess.CompletedProcess[str]:
            commands.append(command)
            assert cwd == SCRIPT.parents[4], 'gitlint runs where its relative custom rules resolve'
            assert capture_output, 'gitlint output is captured for the result'
            assert text, 'gitlint output is decoded as text'
            assert not check, 'gitlint exit status is handled as a refusal'
            return subprocess.CompletedProcess(command, 1, 'UC2 invalid body', '')

        monkeypatch.setattr(integrate.gitflow, 'require_clean', lambda _repo, _log: None)
        monkeypatch.setattr(integrate.gitflow, 'git', git)
        monkeypatch.setattr(integrate.gitflow, 'is_ancestor', lambda *_args: True)
        monkeypatch.setattr(integrate.gitflow, 'rev_parse', lambda *_args: None)
        monkeypatch.setattr(integrate.subprocess, 'run', run)

        #: When
        result, code = integrate.squash(repo, 'lnsd/x', 'origin/main', message, log)

        #: Then
        assert code == integrate.EXIT_REFUSED, 'an invalid message is refused'
        assert result == {
            'status': 'refused',
            'reason': 'gitlint rejected the squash message:\nUC2 invalid body',
            'head_sha': 'head-sha',
        }, 'the refusal reports gitlint violations and the unchanged head'
        assert commands[0][0] == 'gitlint', 'gitlint checks the message before any reset'
        assert '--msg-filename' in commands[0], 'gitlint receives the caller message file'
        assert commands[0][commands[0].index('--ignore') + 1] == (
            'contrib-body-requires-signed-off-by,body-is-missing,body-min-length,body-max-line-length'
        ), 'gitlint leaves sign-off validation to the commit squash adds'
        assert not any(command[:2] == ['git', 'reset'] for command in commands), 'refusal leaves the branch untouched'
        assert not any(command[:2] == ['git', 'push'] for command in commands), 'refusal never pushes'

    def test_missing_gitlint_names_install_recipe_without_reset(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        #: Given
        integrate = _load_integrate(monkeypatch)
        repo = tmp_path / 'repo'
        repo.mkdir()
        message = tmp_path / 'message.txt'
        message.write_text('fix: valid title\n', encoding='utf-8')
        log = tmp_path / 'log'
        log.write_text('', encoding='utf-8')
        monkeypatch.setattr(integrate.shutil, 'which', lambda _name: None)
        monkeypatch.setattr(integrate.gitflow, 'require_clean', lambda _repo, _log: None)

        def git(_repo: Path, _log: Path, *args: str) -> str:
            if args == ('rev-parse', '--absolute-git-dir'):
                return str(tmp_path / 'git')
            return {
                'branch --show-current': 'lnsd/x',
                'rev-parse HEAD': 'head-sha',
                'rev-parse origin/main': 'base-sha',
            }[' '.join(args)]

        monkeypatch.setattr(integrate.gitflow, 'git', git)
        monkeypatch.setattr(integrate.gitflow, 'is_ancestor', lambda *_args: True)
        monkeypatch.setattr(integrate.gitflow, 'rev_parse', lambda *_args: None)
        monkeypatch.setattr(
            integrate.gitflow,
            'run',
            lambda *_args: pytest.fail('squash must not invoke or skip missing gitlint'),
        )

        #: When
        result, code = integrate.squash(repo, 'lnsd/x', 'origin/main', message, log)

        #: Then
        assert code == integrate.EXIT_REFUSED, 'squash refuses when gitlint is unavailable'
        assert 'just install-gitlint' in str(result['reason']), 'the refusal explains how to install gitlint'
        assert result['head_sha'] == 'head-sha', 'the branch head remains unchanged'
