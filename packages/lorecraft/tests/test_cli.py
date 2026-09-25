"""The CLI assembled: the root application, its global options, and the registry that mounts onto it.

These run the command line in process through Typer's `CliRunner`, so they cross module boundaries —
root application, registry, command module, version strings — without needing the console script that
`tests/e2e/` exercises.
"""

import pytest
from typer.testing import CliRunner

from lorecraft import __version__
from lorecraft.cli import build_app
from lorecraft.cli.registry import DuplicateCommandError, register

runner = CliRunner()


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
