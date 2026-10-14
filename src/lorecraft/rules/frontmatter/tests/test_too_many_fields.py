"""`FM013`, `too-many-fields`, over the problems the frontmatter schemas find in a subject's frontmatter.

Every case is a document written as text, read through a fake context that holds it to its schemas as the real
analysis does, under structure specifications decoded from JSON; no file is read from disk.
"""

from textwrap import dedent
from typing import Final

import pytest

from lorecraft.core.num import NonZeroUnsignedInt, UnsignedInt
from lorecraft.core.path import RootRelativePath
from lorecraft.project.schemas import AgentSkillsSchema, FieldCount, FieldLimit, StructureSpecSchema
from lorecraft.project.syntax import LineNumber
from lorecraft.rules.location import Elsewhere, Help, Here, Label, Note
from lorecraft.rules.tests.fake_context import FakeDocumentContext, namespace_spec, structure_spec_path

from ..too_many_fields import TooManyFields

CORPUS_SPEC: Final[RootRelativePath] = structure_spec_path('guide')
"""Where the corpus structure specification lies."""

NAMESPACE_SPEC: Final[RootRelativePath] = structure_spec_path('guide-setup')
"""Where a namespace structure specification under the same corpus lies."""

CORPUS_SOURCE: Final[StructureSpecSchema] = StructureSpecSchema(spec=CORPUS_SPEC)
"""The schema the corpus specification states."""

NAMESPACE_SOURCE: Final[StructureSpecSchema] = StructureSpecSchema(spec=NAMESPACE_SPEC)
"""The schema the namespace specification states."""

MAX_PROPERTIES: Final[str] = '{"frontmatter": {"type": "object", "maxProperties": 1}}'
"""A structure specification whose frontmatter schema allows at most one field."""

MIN_PROPERTIES: Final[str] = '{"frontmatter": {"type": "object", "minProperties": 3}}'
"""A structure specification whose frontmatter schema requires at least three fields."""

TEXT: Final[str] = dedent("""\
    ---
    name: setup
    description: Install the toolkit.
    ---
    # Setup
    """)
"""A document whose frontmatter holds two fields."""

LIMIT: Final[FieldLimit] = FieldLimit(UnsignedInt(1))
"""The most fields `MAX_PROPERTIES` allows."""

FIELD_COUNT: Final[FieldCount] = FieldCount(UnsignedInt(2))
"""The number of fields `TEXT` holds."""

LINE: Final[LineNumber] = LineNumber(NonZeroUnsignedInt(1))
"""The line the rule reports on: it concerns no field."""


@pytest.mark.unit
class TestTooManyFields:
    def test_check_with_more_fields_than_the_schema_allows_reports_it_on_line_1(self) -> None:
        #: Given
        subject = FakeDocumentContext(TEXT, corpus='guide', structure=MAX_PROPERTIES)

        #: When
        occurrences = TooManyFields.check(subject)

        #: Then
        assert occurrences == (TooManyFields(source=CORPUS_SOURCE, line=LINE, limit=LIMIT, field_count=FIELD_COUNT),), (
            "a block past `maxProperties` is one occurrence, on line 1, naming the schema's specification"
        )

    def test_check_with_exactly_the_most_fields_reports_nothing(self) -> None:
        #: Given
        structure = '{"frontmatter": {"type": "object", "maxProperties": 2}}'
        subject = FakeDocumentContext(TEXT, corpus='guide', structure=structure)

        #: When
        occurrences = TooManyFields.check(subject)

        #: Then
        assert occurrences == (), 'a block at the limit holds no more fields than the schema allows'

    def test_check_with_too_few_fields_reports_nothing(self) -> None:
        #: Given
        subject = FakeDocumentContext(TEXT, corpus='guide', structure=MIN_PROPERTIES)

        #: When
        occurrences = TooManyFields.check(subject)

        #: Then
        assert occurrences == (), "a block short of `minProperties` is another rule's condition"

    def test_check_with_two_schemas_reports_each_problem_with_its_own_specification(self) -> None:
        #: Given
        subject = FakeDocumentContext(
            TEXT,
            corpus='guide',
            structure=MAX_PROPERTIES,
            namespaces=(namespace_spec('guide', 'setup', MAX_PROPERTIES),),
        )

        #: When
        occurrences = TooManyFields.check(subject)

        #: Then
        assert occurrences == (
            TooManyFields(source=CORPUS_SOURCE, line=LINE, limit=LIMIT, field_count=FIELD_COUNT),
            TooManyFields(source=NAMESPACE_SOURCE, line=LINE, limit=LIMIT, field_count=FIELD_COUNT),
        ), 'each schema is applied on its own, so each reports the problem under its own specification, in order'

    def test_check_with_a_described_schema_carries_its_description(self) -> None:
        #: Given
        structure = (
            '{"frontmatter": {"type": "object", "maxProperties": 1, '
            '"description": "The fields an agent lists a document by."}}'
        )
        subject = FakeDocumentContext(TEXT, corpus='guide', structure=structure)

        #: When
        occurrences = TooManyFields.check(subject)

        #: Then
        assert occurrences == (
            TooManyFields(
                source=CORPUS_SOURCE,
                line=LINE,
                limit=LIMIT,
                field_count=FIELD_COUNT,
                description='The fields an agent lists a document by.',
            ),
        ), "the root schema's description is carried with the limit and the number of fields"

    def test_message_with_an_occurrence_states_the_count_against_the_limit(self) -> None:
        #: Given
        occurrence = TooManyFields(
            source=CORPUS_SOURCE, line=LINE, limit=FieldLimit(UnsignedInt(2)), field_count=FieldCount(UnsignedInt(3))
        )

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'too many fields (3 > 2)', (
            'the message states the number of fields found against the most allowed'
        )

    def test_labels_with_an_occurrence_name_the_number_of_fields_on_line_1(self) -> None:
        #: Given
        occurrence = TooManyFields(source=CORPUS_SOURCE, line=LINE, limit=LIMIT, field_count=FIELD_COUNT)

        #: When
        labels = occurrence.labels()

        #: Then
        assert labels == (Label(Here(LINE), 'fields over the limit: 1'),), (
            'the label is on line 1, the whole block, and says how many fields are past the limit: 2 is 1 past 1'
        )

    def test_children_without_a_description_point_at_the_specification_only(self) -> None:
        #: Given
        occurrence = TooManyFields(source=CORPUS_SOURCE, line=LINE, limit=LIMIT, field_count=FIELD_COUNT)

        #: When
        children = occurrence.children()

        #: Then
        assert children == (Note('the frontmatter schema is set here', at=Elsewhere(CORPUS_SPEC)),), (
            'the message states the limit, so only the place the schema is stated is left to say'
        )

    def test_children_with_a_description_give_it_as_the_help(self) -> None:
        #: Given
        occurrence = TooManyFields(
            source=CORPUS_SOURCE,
            line=LINE,
            limit=LIMIT,
            field_count=FIELD_COUNT,
            description='The fields an agent lists a document by.',
        )

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note('the frontmatter schema is set here', at=Elsewhere(CORPUS_SPEC)),
            Help('The fields an agent lists a document by.'),
        ), 'the root schema description is shown as the schema wrote it'

    def test_children_with_the_agent_skills_specification_note_no_location(self) -> None:
        #: Given
        occurrence = TooManyFields(source=AgentSkillsSchema(), line=LINE, limit=LIMIT, field_count=FIELD_COUNT)

        #: When
        children = occurrence.children()

        #: Then
        assert children == (Note("the Agent Skills specification states a SKILL.md's frontmatter schema"),), (
            'the Agent Skills specification has no file to point at'
        )
