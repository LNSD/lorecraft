"""The CLI as a user runs it: a real process, the installed package, and whatever git is on the box.

`version --verbose` shells out to `git describe`, so this is the only tier that can observe the probe
at all. This suite runs from the checkout, so the verbose command must report its Git description as
well as the installed version and environment. Every version output is compared to a reviewed snapshot
file under `__snapshots__/`.
"""

from typing import Final

import pytest
from syrupy.assertion import SnapshotAssertion

from lib.cli import run_cli
from lib.snapshot import TextSnapshotExtension
from lorecraft import __version__

# The labelled lines of `version --verbose` whose values differ per checkout, interpreter, machine and install.
_VARYING_FIELDS: Final[tuple[str, ...]] = ('Commit', 'Python', 'Platform', 'Install')


def _redact(output: str) -> str:
    """Swap every value that differs per build, checkout or machine for a placeholder naming it.

    The version becomes ``<version>`` wherever it appears, and each varying labelled line keeps its label and
    its alignment, so the snapshot still pins the layout: ``Commit:   <commit>``.
    """
    lines: list[str] = []
    for line in output.replace(__version__, '<version>').splitlines():
        label, separator, value = line.partition(':')
        if separator and label in _VARYING_FIELDS:
            padding = value[: len(value) - len(value.lstrip())]
            line = f'{label}:{padding}<{label.lower()}>'
        lines.append(line)
    return '\n'.join(lines) + '\n'


@pytest.mark.e2e
class TestInstalledCommandLine:
    def test_no_arguments_prints_the_help_and_exits_nonzero(self) -> None:
        #: Given
        arguments: tuple[str, ...] = ()

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode != 0, 'a bare invocation is a usage error, not a success'
        assert 'Usage:' in result.stdout, 'no_args_is_help prints the help rather than nothing'


@pytest.mark.e2e
class TestVersionSnapshots:
    # The version, the commit and the environment differ per build and per machine, so each test redacts them
    # before comparing, the way an insta filter would; everything else is compared byte for byte.

    def test_version_option_with_long_form_prints_the_short_version(self, snapshot: SnapshotAssertion) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        arguments = ('--version',)

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 0, result.stderr
        assert _redact(result.stdout) == expected, 'the option prints the one-line version'

    def test_version_option_with_short_form_prints_the_short_version(self, snapshot: SnapshotAssertion) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        arguments = ('-V',)

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 0, result.stderr
        assert _redact(result.stdout) == expected, '-V prints the same line as --version'

    def test_version_command_without_verbose_prints_the_short_version(self, snapshot: SnapshotAssertion) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        arguments = ('version',)

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 0, result.stderr
        assert _redact(result.stdout) == expected, 'the plain subcommand prints the same line as the option'

    def test_version_command_with_verbose_reports_the_checkout_commit_and_environment(
        self, snapshot: SnapshotAssertion
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        arguments = ('version', '--verbose')

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 0, result.stderr
        assert _redact(result.stdout) == expected, (
            'run from the checkout, the block carries the commit line as well as the environment'
        )
