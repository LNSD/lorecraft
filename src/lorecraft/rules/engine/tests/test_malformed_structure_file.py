"""`LC003`, `malformed-structure-file`: the engine's diagnostic for this load failure."""

import pytest

from lorecraft.rules.declaration import Severity
from lorecraft.rules.location import Help, Note, WholeSubject

from ..malformed_structure_file import MalformedStructureFile


def _occurrence() -> MalformedStructureFile:
    """One occurrence of `malformed-structure-file`."""
    return MalformedStructureFile(problems=('max_tokens: Extra inputs are not permitted',))


@pytest.mark.unit
class TestMalformedStructureFile:
    def test_code_of_malformed_structure_file_prints_lc003(self) -> None:
        #: Given
        condition = MalformedStructureFile

        #: When
        code = str(condition.CODE)

        #: Then
        assert code == 'LC003', 'the condition holds its place in the engine group'

    def test_severity_of_malformed_structure_file_is_error(self) -> None:
        #: Given
        condition = MalformedStructureFile

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
        assert message == 'structure file does not follow the structure format', (
            'the message states the condition, lowercase, no period'
        )

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
            Note('max_tokens: Extra inputs are not permitted'),
            Help('fix each problem listed'),
        ), 'the facts the occurrence holds are said as notes, and the fix as a help'
