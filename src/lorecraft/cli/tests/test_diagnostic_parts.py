"""The places and marks a diagnostic points at, as the text and JSON outputs read them."""

from typing import Final

import pytest

from lorecraft.core.path import RootRelativePath
from lorecraft.project.syntax import LineNumber
from lorecraft.rules.location import Elsewhere, Help, Here

from ..diagnostic_parts import FilePlace, child_place, format_place, place

_SUBJECT: Final[RootRelativePath] = RootRelativePath.parse('docs/code/a.md')
_SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/code.structure.json')
_OTHER: Final[RootRelativePath] = RootRelativePath.parse('docs/feat/check.md')


def _line(number: int) -> LineNumber:
    return LineNumber.from_int(number)


@pytest.mark.unit
class TestPlace:
    def test_place_with_a_line_of_the_subject_returns_the_subject_at_that_line(self) -> None:
        #: Given
        location = Here(_line(3))

        #: When
        at = place(_SUBJECT, location)

        #: Then
        assert at == FilePlace(_SUBJECT, _line(3)), 'a line of the subject is in the subject'

    def test_place_with_another_file_returns_it_with_no_line(self) -> None:
        #: Given
        location = Elsewhere(_OTHER)

        #: When
        at = place(_SUBJECT, location)

        #: Then
        assert at == FilePlace(_OTHER, None), 'a file named whole has no line'


@pytest.mark.unit
class TestChildPlace:
    def test_child_place_with_a_help_that_points_nowhere_returns_none(self) -> None:
        #: Given
        help_without_place = Help('write it once')

        #: When
        at = child_place(_SUBJECT, help_without_place)

        #: Then
        assert at is None, 'a help with no location has no place, not a place with neither file nor line'

    def test_child_place_with_a_help_that_points_at_a_line_of_another_file_returns_it(self) -> None:
        #: Given
        help_in_other_file = Help('see here', at=Elsewhere(_OTHER, _line(7)))

        #: When
        at = child_place(_SUBJECT, help_in_other_file)

        #: Then
        assert at == FilePlace(_OTHER, _line(7)), 'the file and the line it names'


@pytest.mark.unit
class TestFormatPlace:
    def test_format_place_with_a_line_prints_path_and_line(self) -> None:
        #: Given
        place_at_line = FilePlace(_SUBJECT, _line(3))

        #: When
        text = format_place(place_at_line)

        #: Then
        assert text == 'docs/code/a.md:3', 'a line is printed after the path, joined by a colon'

    def test_format_place_with_a_whole_file_prints_the_path_alone(self) -> None:
        #: Given
        whole_file = FilePlace(_SPEC, None)

        #: When
        text = format_place(whole_file)

        #: Then
        assert text == 'docs/__meta__/code.structure.json', 'a whole file is printed as its path alone'
