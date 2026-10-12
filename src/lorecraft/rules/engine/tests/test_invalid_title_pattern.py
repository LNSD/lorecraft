"""`LC009`, `invalid-title-pattern`: the engine's diagnostic for this load failure."""

import pytest

from lorecraft.rules.declaration import Severity
from lorecraft.rules.location import Note, WholeSubject

from ..invalid_title_pattern import InvalidTitlePattern


def _occurrence() -> InvalidTitlePattern:
    """One occurrence of `invalid-title-pattern`."""
    return InvalidTitlePattern(pattern='[A-Z', problem='unterminated character set at position 0')


@pytest.mark.unit
class TestInvalidTitlePattern:
    def test_code_of_invalid_title_pattern_prints_lc009(self) -> None:
        #: Given
        condition = InvalidTitlePattern

        #: When
        code = str(condition.CODE)

        #: Then
        assert code == 'LC009', 'the condition holds its place in the engine group'

    def test_severity_of_invalid_title_pattern_is_error(self) -> None:
        #: Given
        condition = InvalidTitlePattern

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
        assert message == 'title pattern is not a valid regular expression', (
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
        assert children == (Note("pattern '[A-Z': unterminated character set at position 0"),), (
            'the facts the occurrence holds are said as notes, and the fix as a help'
        )
