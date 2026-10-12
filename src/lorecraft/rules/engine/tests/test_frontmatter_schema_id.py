"""`LC011`, `frontmatter-schema-id`: the engine's diagnostic for this load failure."""

import pytest

from lorecraft.rules.declaration import Severity
from lorecraft.rules.location import Help, WholeSubject

from ..frontmatter_schema_id import FrontmatterSchemaId


def _occurrence() -> FrontmatterSchemaId:
    """One occurrence of `frontmatter-schema-id`."""
    return FrontmatterSchemaId()


@pytest.mark.unit
class TestFrontmatterSchemaId:
    def test_code_of_frontmatter_schema_id_prints_lc011(self) -> None:
        #: Given
        condition = FrontmatterSchemaId

        #: When
        code = str(condition.CODE)

        #: Then
        assert code == 'LC011', 'the condition holds its place in the engine group'

    def test_severity_of_frontmatter_schema_id_is_error(self) -> None:
        #: Given
        condition = FrontmatterSchemaId

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
        assert message == 'frontmatter schema carries $id', 'the message states the condition, lowercase, no period'

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
        assert children == (Help('remove $id from every schema in the frontmatter schema'),), (
            'the facts the occurrence holds are said as notes, and the fix as a help'
        )
