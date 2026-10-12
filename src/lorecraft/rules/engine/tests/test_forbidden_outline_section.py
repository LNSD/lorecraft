"""`LC007`, `forbidden-outline-section`: the engine's diagnostic for this load failure."""

import pytest

from lorecraft.rules.declaration import Severity
from lorecraft.rules.location import Help, Note, WholeSubject

from ..forbidden_outline_section import ForbiddenOutlineSection


def _occurrence() -> ForbiddenOutlineSection:
    """One occurrence of `forbidden-outline-section`."""
    return ForbiddenOutlineSection(sections=('Overview',))


@pytest.mark.unit
class TestForbiddenOutlineSection:
    def test_code_of_forbidden_outline_section_prints_lc007(self) -> None:
        #: Given
        condition = ForbiddenOutlineSection

        #: When
        code = str(condition.CODE)

        #: Then
        assert code == 'LC007', 'the condition holds its place in the engine group'

    def test_severity_of_forbidden_outline_section_is_error(self) -> None:
        #: Given
        condition = ForbiddenOutlineSection

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
        assert message == 'outline names a section the file also forbids', (
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
            Note('named and forbidden: Overview'),
            Help('keep each section in the outline or in the forbidden list, not both'),
        ), 'the facts the occurrence holds are said as notes, and the fix as a help'
