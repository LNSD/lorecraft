"""`LC013`, `untyped-frontmatter-schema`: the engine's diagnostic for this load failure."""

import pytest

from lorecraft.rules.declaration import Severity
from lorecraft.rules.location import Help, WholeSubject

from ..untyped_frontmatter_schema import UntypedFrontmatterSchema


def _occurrence() -> UntypedFrontmatterSchema:
    """One occurrence of `untyped-frontmatter-schema`."""
    return UntypedFrontmatterSchema()


@pytest.mark.unit
class TestUntypedFrontmatterSchema:
    def test_code_of_untyped_frontmatter_schema_prints_lc013(self) -> None:
        #: Given
        condition = UntypedFrontmatterSchema

        #: When
        code = str(condition.CODE)

        #: Then
        assert code == 'LC013', 'the condition holds its place in the engine group'

    def test_severity_of_untyped_frontmatter_schema_is_error(self) -> None:
        #: Given
        condition = UntypedFrontmatterSchema

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
        assert message == 'frontmatter schema does not state "type": "object" at its root', (
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
        assert children == (Help('add "type": "object" to the root of the frontmatter schema'),), (
            'the facts the occurrence holds are said as notes, and the fix as a help'
        )
