"""`LC012`, `foreign-frontmatter-dialect`: the engine's diagnostic for this load failure."""

import pytest

from lorecraft.rules.declaration import Severity
from lorecraft.rules.location import Help, Note, WholeSubject

from ..foreign_frontmatter_dialect import ForeignFrontmatterDialect


def _occurrence() -> ForeignFrontmatterDialect:
    """One occurrence of `foreign-frontmatter-dialect`."""
    return ForeignFrontmatterDialect(dialect="'http://json-schema.org/draft-07/schema#'")


@pytest.mark.unit
class TestForeignFrontmatterDialect:
    def test_code_of_foreign_frontmatter_dialect_prints_lc012(self) -> None:
        #: Given
        condition = ForeignFrontmatterDialect

        #: When
        code = str(condition.CODE)

        #: Then
        assert code == 'LC012', 'the condition holds its place in the engine group'

    def test_severity_of_foreign_frontmatter_dialect_is_error(self) -> None:
        #: Given
        condition = ForeignFrontmatterDialect

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
        assert message == 'frontmatter schema names another JSON Schema dialect', (
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
            Note("$schema holds 'http://json-schema.org/draft-07/schema#'"),
            Help('name https://json-schema.org/draft/2020-12/schema, or leave $schema out'),
        ), 'the facts the occurrence holds are said as notes, and the fix as a help'
