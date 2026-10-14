"""The places and marks a diagnostic points at, as the text and JSON outputs read them."""

from typing import Final

import pytest

from lorecraft.core.num import NonZeroUnsignedInt
from lorecraft.core.path import RootRelativePath
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.context import DocumentFrontmatterOwner
from lorecraft.project.syntax import LineNumber
from lorecraft.rules.frontmatter.duplicate_key import DuplicateKey
from lorecraft.rules.identity import Severity
from lorecraft.rules.location import Elsewhere, Help, Here
from lorecraft.rules.report import RuleDiagnostic

from ..diagnostic_parts import (
    FilePlace,
    LineMark,
    WholeFileMark,
    child_place,
    diagnostic_marks,
    format_place,
    place,
)

_SUBJECT: Final[RootRelativePath] = RootRelativePath.parse('docs/code/a.md')
_SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/code.structure.json')
_OWNER: Final[DocumentFrontmatterOwner] = DocumentFrontmatterOwner(filename=AspectFilename.parse('guide'), spec=_SPEC)
_OTHER: Final[RootRelativePath] = RootRelativePath.parse('docs/feat/check.md')


def _line(number: int) -> LineNumber:
    return LineNumber(NonZeroUnsignedInt(number))


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


@pytest.mark.unit
class TestDiagnosticMarks:
    def test_diagnostic_marks_with_labels_and_children_marks_lines_and_whole_files_apart(self) -> None:
        #: Given
        occurrence = DuplicateKey(owner=_OWNER, line=_line(3), key='name', first_line=_line(2), kept_line=_line(1))
        diagnostic = RuleDiagnostic(_SUBJECT, occurrence, Severity.ERROR)

        #: When
        marks = diagnostic_marks(diagnostic)

        #: Then
        assert marks == [
            LineMark(_SUBJECT, _line(3), 'written again here', primary=True),
            LineMark(_SUBJECT, _line(2), 'first written here', primary=False),
            WholeFileMark(_SPEC, ''),
            LineMark(_SUBJECT, _line(1), '', primary=False),
        ], 'the labels, then each place a note names; only the reported line is primary'

    def test_diagnostic_marks_with_a_note_at_a_line_already_marked_adds_nothing(self) -> None:
        #: Given
        occurrence = DuplicateKey(owner=_OWNER, line=_line(3), key='name', first_line=_line(2), kept_line=_line(2))
        diagnostic = RuleDiagnostic(_SUBJECT, occurrence, Severity.ERROR)

        #: When
        marks = diagnostic_marks(diagnostic)

        #: Then
        assert marks == [
            LineMark(_SUBJECT, _line(3), 'written again here', primary=True),
            LineMark(_SUBJECT, _line(2), 'first written here', primary=False),
            WholeFileMark(_SPEC, ''),
        ], 'the kept line is the first one, which is already marked'
