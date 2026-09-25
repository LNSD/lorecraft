"""The CLI as a user runs it: a real process, the installed package, and whatever git is on the box.

`version --verbose` shells out to `git describe`, so this is the only tier that can observe the probe
at all. This suite runs from the checkout, so the verbose command must report its Git description as
well as the installed version and environment.
"""

import subprocess
import sys
from pathlib import Path

import pytest

from lorecraft import __version__

_CONSOLE_SCRIPT_NAME: str = 'lorecraft.exe' if sys.platform == 'win32' else 'lorecraft'
_COMMAND: tuple[str, ...] = (str(Path(sys.executable).parent / _CONSOLE_SCRIPT_NAME),)


def _run(*arguments: str) -> subprocess.CompletedProcess[str]:
    """Run the installed CLI in a subprocess and capture what it wrote."""
    return subprocess.run([*_COMMAND, *arguments], capture_output=True, text=True, timeout=30)


@pytest.mark.e2e
class TestInstalledCommandLine:
    def test_version_option_with_long_form_prints_the_installed_version(self) -> None:
        #: Given
        arguments = ('--version',)

        #: When
        result = _run(*arguments)

        #: Then
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == f'lorecraft {__version__}', 'the process reports its own metadata'

    def test_version_command_with_verbose_reports_the_checkout_commit_and_environment(self) -> None:
        #: Given
        arguments = ('version', '--verbose')

        #: When
        result = _run(*arguments)

        #: Then
        assert result.returncode == 0, result.stderr
        assert result.stdout.startswith(f'lorecraft {__version__}'), 'the short version leads the block'
        assert 'Commit:' in result.stdout, 'the checkout description is present'
        assert 'Python:' in result.stdout, 'the detailed block survived a real invocation'
        assert 'Platform:' in result.stdout, 'and so did the platform line'
        assert 'Install:' in result.stdout, 'and the install path the probe resolves against'

    def test_no_arguments_prints_the_help_and_exits_nonzero(self) -> None:
        #: Given
        arguments: tuple[str, ...] = ()

        #: When
        result = _run(*arguments)

        #: Then
        assert result.returncode != 0, 'a bare invocation is a usage error, not a success'
        assert 'Usage:' in result.stdout, 'no_args_is_help prints the help rather than nothing'
