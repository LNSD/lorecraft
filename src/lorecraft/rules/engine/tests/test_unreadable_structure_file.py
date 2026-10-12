"""`LC002`, `unreadable-structure-file`: the engine's diagnostic for this load failure."""

import pytest

from lorecraft.rules.declaration import Severity
from lorecraft.rules.location import Help, Note, WholeSubject
from lorecraft.vfs import OsRefusal

from ..unreadable_structure_file import UnreadableStructureFile


def _occurrence() -> UnreadableStructureFile:
    """One occurrence of `unreadable-structure-file`."""
    return UnreadableStructureFile(refusal=OsRefusal.PERMISSION_DENIED)


@pytest.mark.unit
class TestUnreadableStructureFile:
    def test_code_of_unreadable_structure_file_prints_lc002(self) -> None:
        #: Given
        condition = UnreadableStructureFile

        #: When
        code = str(condition.CODE)

        #: Then
        assert code == 'LC002', 'the condition holds its place in the engine group'

    def test_severity_of_unreadable_structure_file_is_error(self) -> None:
        #: Given
        condition = UnreadableStructureFile

        #: When
        severity = condition.SEVERITY

        #: Then
        assert severity is Severity.ERROR, 'a load failure always fails the run'

    def test_message_of_an_occurrence_names_the_condition(self) -> None:
        #: Given
        occurrence = _occurrence()

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'structure file cannot be read', 'the message states the condition, lowercase, no period'

    def test_primary_of_an_occurrence_is_the_whole_subject(self) -> None:
        #: Given
        occurrence = _occurrence()

        #: When
        primary = occurrence.primary()

        #: Then
        assert primary == WholeSubject(), 'the failure is not at a line'

    def test_children_of_an_occurrence_say_what_was_found_and_how_to_fix_it(self) -> None:
        #: Given
        occurrence = _occurrence()

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note('the operating system refused the read: permission denied'),
            Help('make the file readable by the process that runs the check'),
        ), 'the facts the occurrence holds are said as notes, and the fix as a help'

    def test_children_of_an_occurrence_with_no_regular_file_say_so_and_how_to_restore_it(self) -> None:
        #: Given
        occurrence = UnreadableStructureFile(refusal=None)

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note('the file is not a regular file the check can find'),
            Help('restore the file as a regular file inside the repository'),
        ), 'with no refusal to name, the note says what stands where the file should be'
