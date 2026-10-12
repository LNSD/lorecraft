"""`LC017`, `unreadable-skill-file`: the engine's diagnostic for this load failure."""

import pytest

from lorecraft.core.path import RootRelativePath
from lorecraft.rules.declaration import Severity
from lorecraft.rules.location import EntryHelp, EntryNote, WholeSubject
from lorecraft.vfs import OsRefusal

from ..__ruleset__ import RefusedOperation
from ..unreadable_skill_file import UnreadableSkillFile


def _occurrence() -> UnreadableSkillFile:
    """One occurrence of `unreadable-skill-file`."""
    return UnreadableSkillFile(
        operation=RefusedOperation.LIST,
        failed_at=RootRelativePath.parse('.agents/skills'),
        refusal=OsRefusal.PERMISSION_DENIED,
    )


@pytest.mark.unit
class TestUnreadableSkillFile:
    def test_code_of_unreadable_skill_file_prints_lc017(self) -> None:
        #: Given
        condition = UnreadableSkillFile

        #: When
        code = str(condition.CODE)

        #: Then
        assert code == 'LC017', 'the condition holds its place in the engine group'

    def test_severity_of_unreadable_skill_file_is_error(self) -> None:
        #: Given
        condition = UnreadableSkillFile

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
        assert message == 'skill file cannot be resolved', 'the message states the condition, lowercase, no period'

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
            EntryNote('cannot list .agents/skills: permission denied'),
            EntryHelp('make the `SKILL.md`, and what it links to, readable by the process that runs the check'),
        ), 'the facts the occurrence holds are said as notes, and the fix as a help'
