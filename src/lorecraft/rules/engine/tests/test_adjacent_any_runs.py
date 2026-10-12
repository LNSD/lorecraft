"""`LC008`, `adjacent-any-runs`: the engine's diagnostic for this load failure."""

import pytest

from lorecraft.rules.declaration import Severity
from lorecraft.rules.location import Help, WholeSubject

from ..adjacent_any_runs import AdjacentAnyRuns


def _occurrence() -> AdjacentAnyRuns:
    """One occurrence of `adjacent-any-runs`."""
    return AdjacentAnyRuns()


@pytest.mark.unit
class TestAdjacentAnyRuns:
    def test_code_of_adjacent_any_runs_prints_lc008(self) -> None:
        #: Given
        condition = AdjacentAnyRuns

        #: When
        code = str(condition.CODE)

        #: Then
        assert code == 'LC008', 'the condition holds its place in the engine group'

    def test_severity_of_adjacent_any_runs_is_error(self) -> None:
        #: Given
        condition = AdjacentAnyRuns

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
        assert message == 'outline places two any runs side by side', (
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
        assert children == (Help('state one any run in their place'),), (
            'the facts the occurrence holds are said as notes, and the fix as a help'
        )
