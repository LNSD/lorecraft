"""`LC002`, `unreadable-path`: the engine's diagnostic for every path the operating system refuses to read."""

import pytest

from lorecraft.core.path import RootRelativePath
from lorecraft.rules.declaration import Severity
from lorecraft.rules.location import EntryHelp, EntryNote, WholeSubject
from lorecraft.vfs import OsRefusal

from ..__ruleset__ import RefusedOperation
from ..unreadable_path import NotARegularFile, Refused, UnreadablePath

_ACCESS_HELP = EntryHelp('make the path, and what it links to, accessible to the process that runs the check')


def _occurrence() -> UnreadablePath:
    """One occurrence of `unreadable-path`."""
    return UnreadablePath(
        failed_at=RootRelativePath.parse('.agents/skills'),
        cause=Refused(operation=RefusedOperation.LIST, refusal=OsRefusal.PERMISSION_DENIED),
    )


@pytest.mark.unit
class TestUnreadablePath:
    def test_code_of_unreadable_path_prints_lc002(self) -> None:
        #: Given
        condition = UnreadablePath

        #: When
        code = str(condition.CODE)

        #: Then
        assert code == 'LC002', 'the condition holds its place in the engine group'

    def test_severity_of_unreadable_path_is_error(self) -> None:
        #: Given
        condition = UnreadablePath

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
        assert message == 'path cannot be read', 'the message states the condition, lowercase, no period'

    def test_primary_of_an_occurrence_is_the_whole_subject(self) -> None:
        #: Given
        occurrence = _occurrence()

        #: When
        primary = occurrence.primary()

        #: Then
        assert primary == WholeSubject(), 'the failure is not at a line'

    def test_children_of_a_refused_read_name_the_file_and_the_reason(self) -> None:
        #: Given
        occurrence = UnreadablePath(
            failed_at=RootRelativePath.parse('docs/__meta__/code.structure.json'),
            cause=Refused(operation=RefusedOperation.READ, refusal=OsRefusal.PERMISSION_DENIED),
        )

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            EntryNote('cannot read docs/__meta__/code.structure.json: permission denied'),
            _ACCESS_HELP,
        ), 'the operation, the path and the refusal are said as a note, and the fix as a help'

    def test_children_of_a_refused_listing_name_the_directory_and_the_reason(self) -> None:
        #: Given
        occurrence = UnreadablePath(
            failed_at=RootRelativePath.parse('docs/code'),
            cause=Refused(operation=RefusedOperation.LIST, refusal=OsRefusal.PERMISSION_DENIED),
        )

        #: When
        children = occurrence.children()

        #: Then
        assert children == (EntryNote('cannot list docs/code: permission denied'), _ACCESS_HELP), (
            'a corpus directory is named by its path, as every other directory'
        )

    def test_children_of_a_refused_resolution_name_the_path_it_was_refused_at(self) -> None:
        #: Given
        occurrence = UnreadablePath(
            failed_at=RootRelativePath.parse('texts'),
            cause=Refused(operation=RefusedOperation.RESOLVE, refusal=OsRefusal.PERMISSION_DENIED),
        )

        #: When
        children = occurrence.children()

        #: Then
        assert children == (EntryNote('cannot resolve texts: permission denied'), _ACCESS_HELP), (
            'the path on the way is named, not the one that was being reached'
        )

    def test_children_of_a_refused_inspection_name_the_path_it_was_refused_at(self) -> None:
        #: Given
        occurrence = UnreadablePath(
            failed_at=RootRelativePath.parse('.agents/skills/audit'),
            cause=Refused(operation=RefusedOperation.INSPECT, refusal=OsRefusal.PERMISSION_DENIED),
        )

        #: When
        children = occurrence.children()

        #: Then
        assert children == (EntryNote('cannot inspect .agents/skills/audit: permission denied'), _ACCESS_HELP), (
            'the operation is named with the verb of what the operating system refused'
        )

    def test_children_of_an_occurrence_with_no_regular_file_say_so_and_how_to_restore_it(self) -> None:
        #: Given
        occurrence = UnreadablePath(
            failed_at=RootRelativePath.parse('docs/__meta__/code.structure.json'),
            cause=NotARegularFile(),
        )

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            EntryNote('cannot read docs/__meta__/code.structure.json: no regular file the check can find'),
            EntryHelp('restore the file as a regular file inside the repository'),
        ), 'with no refusal to name, the note says what stands where the file should be'
