"""`LC004`, `unusable-structure-file`: the engine's diagnostic for a structure file whose rules cannot be applied."""

import pytest

from lorecraft.project.schemas.section_name import SectionName
from lorecraft.project.schemas.structure_file import JSON_SCHEMA_DIALECT
from lorecraft.rules.identity import Severity
from lorecraft.rules.location import Help, Note, Subdiagnostic, WholeSubject

from ..unusable_structure_file import (
    AdjacentAnyRuns,
    Cause,
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

_CASES: list[tuple[Cause, str, tuple[Subdiagnostic, ...]]] = [
    (
        RepeatedOutlineSection(sections=(SectionName('Details'), SectionName('Overview'))),
        'outline names a section more than once',
        (Note('repeated: Details, Overview'), Help('name each section once')),
    ),
    (
        RepeatedForbiddenSection(sections=(SectionName('Draft'),)),
        'a section is forbidden more than once',
        (Note('repeated: Draft'), Help('forbid each section once')),
    ),
    (
        ForbiddenOutlineSection(sections=(SectionName('Overview'),)),
        'outline names a section the file also forbids',
        (
            Note('named and forbidden: Overview'),
            Help('keep each section in the outline or in the forbidden list, not both'),
        ),
    ),
    (
        AdjacentAnyRuns(),
        'outline places two any runs side by side',
        (Help('state one any run in their place'),),
    ),
    (
        InvalidTitlePattern(pattern='[A-Z', problem='unterminated character set at position 0'),
        'title pattern is not a valid regular expression',
        (Note("pattern '[A-Z': unterminated character set at position 0"),),
    ),
    (
        InvalidFrontmatterSchema(problem="'name' is not of type 'array'"),
        'frontmatter schema is not a valid JSON Schema',
        (Note("'name' is not of type 'array'"),),
    ),
    (
        FrontmatterSchemaId(),
        'frontmatter schema carries $id',
        (Help('remove $id from every schema in the frontmatter schema'),),
    ),
    (
        ForeignFrontmatterDialect(dialect="'http://json-schema.org/draft-07/schema#'"),
        'frontmatter schema names another JSON Schema dialect',
        (
            Note("$schema holds 'http://json-schema.org/draft-07/schema#'"),
            Help(f'name {JSON_SCHEMA_DIALECT}, or leave $schema out'),
        ),
    ),
    (
        UnresolvableFrontmatterSchemaRef(ref="'#/$defs/missing'"),
        'frontmatter schema holds a $ref that does not resolve inside it',
        (
            Note("$ref holds '#/$defs/missing'"),
            Help('point every $ref at a location inside the frontmatter schema, such as #/$defs/name'),
        ),
    ),
    (
        UntypedFrontmatterSchema(),
        'frontmatter schema does not state "type": "object" at its root',
        (Help('add "type": "object" to the root of the frontmatter schema'),),
    ),
]
"""Each case with the message and the sub-diagnostics it renders."""

_IDS: list[str] = [type(cause).__name__ for cause, _message, _children in _CASES]


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

    @pytest.mark.parametrize(('cause', 'expected', 'children'), _CASES, ids=_IDS)
    def test_message_of_a_case_names_the_case(
        self, cause: Cause, expected: str, children: tuple[Subdiagnostic, ...]
    ) -> None:
        #: Given
        occurrence = UnusableStructureFile(cause=cause)

        #: When
        message = occurrence.message()

        #: Then
        assert message == expected, 'the message states the case, lowercase, no period'

    @pytest.mark.parametrize(('cause', 'message', 'expected'), _CASES, ids=_IDS)
    def test_children_of_a_case_say_what_was_found_and_how_to_fix_it(
        self, cause: Cause, message: str, expected: tuple[Subdiagnostic, ...]
    ) -> None:
        #: Given
        occurrence = UnusableStructureFile(cause=cause)

        #: When
        children = occurrence.children()

        #: Then
        assert children == expected, 'the facts the case holds are said as notes, and the fix as a help'
