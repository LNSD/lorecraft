"""`LC005`, `repeated-outline-section`: the engine's diagnostic for this load failure."""

import pytest

from lorecraft.rules.declaration import Severity
from lorecraft.rules.location import Help, Note, WholeSubject

from ..repeated_outline_section import RepeatedOutlineSection


def _occurrence() -> RepeatedOutlineSection:
    """One occurrence of `repeated-outline-section`."""
    return RepeatedOutlineSection(sections=('Details', 'Overview'))


@pytest.mark.unit
class TestRepeatedOutlineSection:
    def test_code_of_repeated_outline_section_prints_lc005(self) -> None:
        #: Given
        condition = RepeatedOutlineSection

        #: When
        code = str(condition.CODE)

        #: Then
        assert code == 'LC005', 'the condition holds its place in the engine group'

    def test_severity_of_repeated_outline_section_is_error(self) -> None:
        #: Given
        condition = RepeatedOutlineSection

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
        assert message == 'outline names a section more than once', (
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
            Note('repeated: Details, Overview'),
            Help('name each section once'),
        ), 'the facts the occurrence holds are said as notes, and the fix as a help'
