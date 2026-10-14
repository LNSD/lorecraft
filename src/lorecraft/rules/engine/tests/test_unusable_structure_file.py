"""`LC004`, `unusable-structure-file`: the engine's diagnostic for a structure file whose rules cannot be applied."""

import pytest

from lorecraft.project.schemas import JSON_SCHEMA_DIALECT, SectionName
from lorecraft.rules.identity import Severity
from lorecraft.rules.location import Help, Note, WholeSubject

from ..unusable_structure_file import (
    AdjacentAnyRuns,
    ForbiddenOutlineSection,
    ForeignFrontmatterDialect,
    FrontmatterSchemaId,
    InvalidFrontmatterSchema,
    InvalidTitlePattern,
    RepeatedForbiddenSection,
    RepeatedOutlineSection,
    UnresolvableFrontmatterSchemaRef,
    UntypedFrontmatterSchema,
    UnusableStructureFile,
)


@pytest.mark.unit
class TestUnusableStructureFile:
    def test_code_of_unusable_structure_file_prints_lc004(self) -> None:
        #: Given
        condition = UnusableStructureFile

        #: When
        code = str(condition.CODE)

        #: Then
        assert code == 'LC004', 'the condition holds its place in the engine group'

    def test_severity_of_unusable_structure_file_is_error(self) -> None:
        #: Given
        condition = UnusableStructureFile

        #: When
        severity = condition.SEVERITY

        #: Then
        assert severity is Severity.ERROR, 'a load failure always fails the run'

    def test_primary_of_an_occurrence_is_the_whole_subject(self) -> None:
        #: Given
        occurrence = UnusableStructureFile(cause=AdjacentAnyRuns())

        #: When
        primary = occurrence.primary()

        #: Then
        assert primary == WholeSubject(), 'the failure is not at a line'

    def test_message_of_repeated_outline_section_names_the_case(self) -> None:
        #: Given
        occurrence = UnusableStructureFile(
            cause=RepeatedOutlineSection(sections=(SectionName('Details'), SectionName('Overview')))
        )

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'outline names a section more than once', 'the message states the case, lowercase, no period'

    def test_children_of_repeated_outline_section_say_what_was_found_and_how_to_fix_it(self) -> None:
        #: Given
        occurrence = UnusableStructureFile(
            cause=RepeatedOutlineSection(sections=(SectionName('Details'), SectionName('Overview')))
        )

        #: When
        children = occurrence.children()

        #: Then
        assert children == (Note('repeated: Details, Overview'), Help('name each section once')), (
            'the facts the case holds are said as notes, and the fix as a help'
        )

    def test_message_of_repeated_forbidden_section_names_the_case(self) -> None:
        #: Given
        occurrence = UnusableStructureFile(cause=RepeatedForbiddenSection(sections=(SectionName('Draft'),)))

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'a section is forbidden more than once', 'the message states the case, lowercase, no period'

    def test_children_of_repeated_forbidden_section_say_what_was_found_and_how_to_fix_it(self) -> None:
        #: Given
        occurrence = UnusableStructureFile(cause=RepeatedForbiddenSection(sections=(SectionName('Draft'),)))

        #: When
        children = occurrence.children()

        #: Then
        assert children == (Note('repeated: Draft'), Help('forbid each section once')), (
            'the facts the case holds are said as notes, and the fix as a help'
        )

    def test_message_of_forbidden_outline_section_names_the_case(self) -> None:
        #: Given
        occurrence = UnusableStructureFile(cause=ForbiddenOutlineSection(sections=(SectionName('Overview'),)))

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'outline names a section the file also forbids', (
            'the message states the case, lowercase, no period'
        )

    def test_children_of_forbidden_outline_section_say_what_was_found_and_how_to_fix_it(self) -> None:
        #: Given
        occurrence = UnusableStructureFile(cause=ForbiddenOutlineSection(sections=(SectionName('Overview'),)))

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note('named and forbidden: Overview'),
            Help('keep each section in the outline or in the forbidden list, not both'),
        ), 'the facts the case holds are said as notes, and the fix as a help'

    def test_message_of_adjacent_any_runs_names_the_case(self) -> None:
        #: Given
        occurrence = UnusableStructureFile(cause=AdjacentAnyRuns())

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'outline places two any runs side by side', (
            'the message states the case, lowercase, no period'
        )

    def test_children_of_adjacent_any_runs_say_what_was_found_and_how_to_fix_it(self) -> None:
        #: Given
        occurrence = UnusableStructureFile(cause=AdjacentAnyRuns())

        #: When
        children = occurrence.children()

        #: Then
        assert children == (Help('state one any run in their place'),), (
            'the facts the case holds are said as notes, and the fix as a help'
        )

    def test_message_of_invalid_title_pattern_names_the_case(self) -> None:
        #: Given
        occurrence = UnusableStructureFile(
            cause=InvalidTitlePattern(pattern='[A-Z', problem='unterminated character set at position 0')
        )

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'title pattern is not a valid regular expression', (
            'the message states the case, lowercase, no period'
        )

    def test_children_of_invalid_title_pattern_say_what_was_found_and_how_to_fix_it(self) -> None:
        #: Given
        occurrence = UnusableStructureFile(
            cause=InvalidTitlePattern(pattern='[A-Z', problem='unterminated character set at position 0')
        )

        #: When
        children = occurrence.children()

        #: Then
        assert children == (Note("pattern '[A-Z': unterminated character set at position 0"),), (
            'the facts the case holds are said as notes, and the fix as a help'
        )

    def test_message_of_invalid_frontmatter_schema_names_the_case(self) -> None:
        #: Given
        occurrence = UnusableStructureFile(cause=InvalidFrontmatterSchema(problem="'name' is not of type 'array'"))

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'frontmatter schema is not a valid JSON Schema', (
            'the message states the case, lowercase, no period'
        )

    def test_children_of_invalid_frontmatter_schema_say_what_was_found_and_how_to_fix_it(self) -> None:
        #: Given
        occurrence = UnusableStructureFile(cause=InvalidFrontmatterSchema(problem="'name' is not of type 'array'"))

        #: When
        children = occurrence.children()

        #: Then
        assert children == (Note("'name' is not of type 'array'"),), (
            'the facts the case holds are said as notes, and the fix as a help'
        )

    def test_message_of_frontmatter_schema_id_names_the_case(self) -> None:
        #: Given
        occurrence = UnusableStructureFile(cause=FrontmatterSchemaId())

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'frontmatter schema carries $id', 'the message states the case, lowercase, no period'

    def test_children_of_frontmatter_schema_id_say_what_was_found_and_how_to_fix_it(self) -> None:
        #: Given
        occurrence = UnusableStructureFile(cause=FrontmatterSchemaId())

        #: When
        children = occurrence.children()

        #: Then
        assert children == (Help('remove $id from every schema in the frontmatter schema'),), (
            'the facts the case holds are said as notes, and the fix as a help'
        )

    def test_message_of_foreign_frontmatter_dialect_names_the_case(self) -> None:
        #: Given
        occurrence = UnusableStructureFile(
            cause=ForeignFrontmatterDialect(dialect="'http://json-schema.org/draft-07/schema#'")
        )

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'frontmatter schema names another JSON Schema dialect', (
            'the message states the case, lowercase, no period'
        )

    def test_children_of_foreign_frontmatter_dialect_say_what_was_found_and_how_to_fix_it(self) -> None:
        #: Given
        occurrence = UnusableStructureFile(
            cause=ForeignFrontmatterDialect(dialect="'http://json-schema.org/draft-07/schema#'")
        )

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note("$schema holds 'http://json-schema.org/draft-07/schema#'"),
            Help(f'name {JSON_SCHEMA_DIALECT}, or leave $schema out'),
        ), 'the facts the case holds are said as notes, and the fix as a help'

    def test_message_of_unresolvable_frontmatter_schema_ref_names_the_case(self) -> None:
        #: Given
        occurrence = UnusableStructureFile(cause=UnresolvableFrontmatterSchemaRef(ref="'#/$defs/missing'"))

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'frontmatter schema holds a $ref that does not resolve inside it', (
            'the message states the case, lowercase, no period'
        )

    def test_children_of_unresolvable_frontmatter_schema_ref_say_what_was_found_and_how_to_fix_it(self) -> None:
        #: Given
        occurrence = UnusableStructureFile(cause=UnresolvableFrontmatterSchemaRef(ref="'#/$defs/missing'"))

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note("$ref holds '#/$defs/missing'"),
            Help('point every $ref at a location inside the frontmatter schema, such as #/$defs/name'),
        ), 'the facts the case holds are said as notes, and the fix as a help'

    def test_message_of_untyped_frontmatter_schema_names_the_case(self) -> None:
        #: Given
        occurrence = UnusableStructureFile(cause=UntypedFrontmatterSchema())

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'frontmatter schema does not state "type": "object" at its root', (
            'the message states the case, lowercase, no period'
        )

    def test_children_of_untyped_frontmatter_schema_say_what_was_found_and_how_to_fix_it(self) -> None:
        #: Given
        occurrence = UnusableStructureFile(cause=UntypedFrontmatterSchema())

        #: When
        children = occurrence.children()

        #: Then
        assert children == (Help('add "type": "object" to the root of the frontmatter schema'),), (
            'the facts the case holds are said as notes, and the fix as a help'
        )
