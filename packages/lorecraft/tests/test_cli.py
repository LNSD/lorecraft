"""The CLI assembled: the root application, its global options, and the registry that mounts onto it.

These run the command line in process through Typer's `CliRunner`, so they cross module boundaries —
root application, registry, command module, version strings, the scan and the model load behind `inspect`
— without needing the console script that `tests/e2e/` exercises. `inspect` reads a real tree under
`tmp_path`.
"""

import json
import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from lorecraft import __version__
from lorecraft.cli import build_app
from lorecraft.cli.registry import DuplicateCommandError, register

runner = CliRunner()


@pytest.fixture(scope='function')
def workspace(tmp_path: Path) -> Path:
    """A workspace root with a `code` corpus of one document and one skill, linked from `.claude/skills`."""
    (tmp_path / 'docs' / '__meta__').mkdir(parents=True)
    (tmp_path / 'docs' / '__meta__' / 'code.md').write_text('# Code\n')
    (tmp_path / 'docs' / 'code').mkdir()
    (tmp_path / 'docs' / 'code' / 'logging.md').write_text('# Logging\n')
    (tmp_path / '.agents' / 'skills' / 'alpha').mkdir(parents=True)
    (tmp_path / '.agents' / 'skills' / 'alpha' / 'SKILL.md').write_text('---\n')
    (tmp_path / '.claude').mkdir()
    (tmp_path / '.claude' / 'skills').symlink_to('../.agents/skills')
    return tmp_path


@pytest.fixture(scope='function')
def malformed_schema_workspace(workspace: Path) -> Path:
    """The workspace with a `code` header schema that is valid JSON but not a well-formed JSON Schema."""
    (workspace / 'docs' / '__meta__' / 'code.header.json').write_text('{"type": 5}\n')
    return workspace


@pytest.fixture(scope='function')
def unreadable_workspace(tmp_path: Path) -> Iterator[Path]:
    """A workspace root whose `docs/` refuses listing, restored afterwards so pytest can clean it up."""
    docs = tmp_path / 'docs'
    docs.mkdir()
    docs.chmod(0o000)
    yield tmp_path
    docs.chmod(0o700)


def _unused_handler() -> None:
    """Stand-in handler for a registration that must be rejected before it is ever mounted."""


@pytest.mark.it
class TestVersionOption:
    def test_version_option_long_form_prints_the_short_version(self) -> None:
        #: Given
        app = build_app()

        #: When
        result = runner.invoke(app, ['--version'])

        #: Then
        assert result.exit_code == 0, result.output
        assert result.output.strip() == f'lorecraft {__version__}', 'the option prints the short version'

    def test_version_option_with_short_form_exits_successfully_and_prints_the_version(self) -> None:
        #: Given
        app = build_app()

        #: When
        result = runner.invoke(app, ['-V'])

        #: Then
        assert result.exit_code == 0, result.output
        assert result.output.strip() == f'lorecraft {__version__}', '-V prints the short version'


@pytest.mark.it
class TestVersionCommand:
    def test_version_command_without_verbose_prints_one_line(self) -> None:
        #: Given
        app = build_app()

        #: When
        result = runner.invoke(app, ['version'])

        #: Then
        assert result.exit_code == 0, result.output
        assert result.output.strip() == f'lorecraft {__version__}', 'the plain command prints one line'


@pytest.mark.it
class TestInspectCommand:
    def test_inspect_with_a_workspace_root_draws_its_model(self, workspace: Path) -> None:
        #: Given
        app = build_app()
        arguments = ['inspect', str(workspace)]

        #: When
        result = runner.invoke(app, arguments)

        #: Then
        assert result.exit_code == 0, result.output
        lines = result.output.splitlines()
        assert lines[0] == str(workspace.resolve()), 'the tree is headed by the resolved root'
        assert '│           └── logging.md [code]' in lines, 'a rule document sits under its corpus, with its spec'
        assert '│   └── claude-code: .claude/skills -> .agents/skills' in lines, (
            'the linked agent skills directory shows where it leads'
        )

    def test_inspect_with_json_prints_the_model_as_one_json_document(self, workspace: Path) -> None:
        #: Given
        app = build_app()
        arguments = ['inspect', str(workspace), '--json']

        #: When
        result = runner.invoke(app, arguments)

        #: Then
        assert result.exit_code == 0, result.output
        document = json.loads(result.output)
        assert document['root'] == str(workspace.resolve()), 'the root is reported resolved'
        assert [corpus['name'] for corpus in document['corpora']] == ['code'], 'the one spec-backed corpus is found'
        assert [skill['name'] for skill in document['skills']] == ['alpha'], 'the one skill is found'

    def test_inspect_with_a_malformed_header_schema_exits_one_and_names_it(
        self, malformed_schema_workspace: Path
    ) -> None:
        #: Given
        app = build_app()
        arguments = ['inspect', str(malformed_schema_workspace)]

        #: When
        result = runner.invoke(app, arguments)

        #: Then
        assert result.exit_code == 1, result.output
        assert 'error: invalid schema docs/__meta__/code.header.json' in result.output, (
            'the failure names the schema the load rejected'
        )

    def test_inspect_without_a_root_scans_the_current_directory(
        self, workspace: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        #: Given
        app = build_app()
        monkeypatch.chdir(workspace)
        arguments = ['inspect']

        #: When
        result = runner.invoke(app, arguments)

        #: Then
        assert result.exit_code == 0, result.output
        assert result.output.splitlines()[0] == str(workspace.resolve()), 'the root defaults to the working directory'

    def test_inspect_with_a_missing_root_exits_with_a_usage_error(self, tmp_path: Path) -> None:
        #: Given
        app = build_app()
        arguments = ['inspect', str(tmp_path / 'missing')]

        #: When
        result = runner.invoke(app, arguments)

        #: Then
        assert result.exit_code == 2, 'a root that does not exist is rejected before any scan'

    @pytest.mark.skipif(os.geteuid() == 0, reason='root ignores directory permissions')
    def test_inspect_with_an_unreadable_directory_exits_one_and_names_it(self, unreadable_workspace: Path) -> None:
        #: Given
        app = build_app()
        arguments = ['inspect', str(unreadable_workspace)]

        #: When
        result = runner.invoke(app, arguments)

        #: Then
        assert result.exit_code == 1, result.output
        assert 'error: cannot snapshot docs' in result.output, 'the failure names the path the scan stopped at'


@pytest.mark.it
class TestCommandRouting:
    def test_build_app_when_called_mounts_every_discovered_subcommand(self) -> None:
        #: Given
        app = build_app()

        #: When
        result = runner.invoke(app, ['--help'])

        #: Then
        assert result.exit_code == 0, result.output
        assert 'version' in result.output, 'discovery mounted the one registered subcommand'

    def test_register_with_a_name_already_taken_raises_duplicate_command_error(self) -> None:
        #: Given
        name = 'version'

        #: When
        with pytest.raises(DuplicateCommandError) as exc_info:
            register(name)(_unused_handler)

        #: Then
        assert name in str(exc_info.value), 'the error names the subcommand that was already registered'
