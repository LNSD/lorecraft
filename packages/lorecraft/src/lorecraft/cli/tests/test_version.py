"""The version strings themselves: pure formatting, with no git and no CLI around it."""

import pytest

from lorecraft import __version__
from lorecraft.cli.version import detailed_version, short_version


@pytest.mark.unit
class TestShortVersion:
    def test_short_version_when_called_returns_the_program_name_and_installed_version(self) -> None:
        #: Given
        expected = f'lorecraft {__version__}'

        #: When
        text = short_version()

        #: Then
        assert text == expected, 'the short version is the program name and the installed version'


@pytest.mark.unit
class TestDetailedVersion:
    # `git describe` belongs to `git_description`, which is why this tier can format a detailed
    # version at all: the commit arrives as a string, so nothing here spawns a subprocess.
    def test_detailed_version_with_a_commit_reports_it_under_the_short_line(self) -> None:
        #: Given
        # a description as `git describe` returns it on a dirty tree
        commit = 'v0.1.0-2-g93b1ed1-dirty'

        #: When
        text = detailed_version(commit)

        #: Then
        assert text.splitlines()[0] == f'lorecraft {__version__}', 'the short version stays the first line'
        assert text.splitlines()[1] == f'Commit:   {commit}', 'the commit is reported directly under it'

    def test_detailed_version_without_a_commit_omits_the_commit_line(self) -> None:
        #: Given
        commit = None

        #: When
        text = detailed_version(commit)

        #: Then
        assert 'Commit:' not in text, 'an absent checkout prints no commit line at all'

    def test_detailed_version_without_a_commit_reports_interpreter_platform_and_install_path(self) -> None:
        #: Given
        commit = None

        #: When
        text = detailed_version(commit)

        #: Then
        assert 'Python:' in text, 'the interpreter is what a reproduction usually turns on'
        assert 'Platform:' in text, 'the platform is reported for the same reason'
        assert 'Install:' in text, 'the install path distinguishes a checkout from a wheel'
