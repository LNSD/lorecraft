"""`LC006`, `repeated-forbidden-section`: the engine's diagnostic for this load failure."""

import pytest

from lorecraft.rules.declaration import Severity
from lorecraft.rules.location import Help, Note, WholeSubject

from ..repeated_forbidden_section import RepeatedForbiddenSection


def _occurrence() -> RepeatedForbiddenSection:
    """One occurrence of `repeated-forbidden-section`."""
    return RepeatedForbiddenSection(sections=('Draft',))


@pytest.mark.unit
class TestRepeatedForbiddenSection:
    def test_code_of_repeated_forbidden_section_prints_lc006(self) -> None:
        #: Given
        condition = RepeatedForbiddenSection

        #: When
        code = str(condition.CODE)

        #: Then
        assert code == 'LC006', 'the condition holds its place in the engine group'

    def test_severity_of_repeated_forbidden_section_is_error(self) -> None:
        #: Given
        condition = RepeatedForbiddenSection

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
        assert message == 'a section is forbidden more than once', (
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
            Note('repeated: Draft'),
            Help('forbid each section once'),
        ), 'the facts the occurrence holds are said as notes, and the fix as a help'
