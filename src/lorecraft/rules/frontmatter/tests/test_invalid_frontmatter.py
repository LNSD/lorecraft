"""`FM010`, `invalid-frontmatter`, over the problems the frontmatter schemas find in a subject's frontmatter.

Every case is a document or a `SKILL.md` written as text, read through a fake context that holds it to its schemas as
the real analysis does, under structure files decoded from JSON; no file is read from disk.

No skill appears in the `check` cases: the Agent Skills specification places every problem it finds on a field, so a
skill's frontmatter breaks no constraint over the whole block, and the note such an occurrence would carry is tested on
its own below.
"""

from textwrap import dedent
from typing import Final

import pytest

from lorecraft.core.num import NonZeroUnsignedInt, UnsignedInt
from lorecraft.core.path import RootRelativePath
from lorecraft.project.schemas import (
    AgentSkillsSchema,
    BlockProblem,
    FieldCount,
    OtherBlockConstraint,
    StructureSpecSchema,
)
from lorecraft.project.syntax import LineNumber
from lorecraft.rules.location import Elsewhere, Help, Note
from lorecraft.rules.tests.fake_context import FakeDocumentContext, namespace_spec, structure_spec_path

from ..invalid_frontmatter import InvalidFrontmatter

CORPUS_SPEC: Final[RootRelativePath] = structure_spec_path('guide')
"""Where the corpus structure file lies."""

NAMESPACE_SPEC: Final[RootRelativePath] = structure_spec_path('guide-setup')
"""Where a namespace structure file under the same corpus lies."""

CORPUS_SOURCE: Final[StructureSpecSchema] = StructureSpecSchema(spec=CORPUS_SPEC)
"""The schema the corpus meta spec states."""

NAMESPACE_SOURCE: Final[StructureSpecSchema] = StructureSpecSchema(spec=NAMESPACE_SPEC)
"""The schema the namespace meta spec states."""

AGENT_SKILLS_SOURCE: Final[AgentSkillsSchema] = AgentSkillsSchema()
"""The schema the Agent Skills specification states, which governs a skill."""

FORBID_NAME: Final[str] = '{"frontmatter": {"type": "object", "not": {"required": ["name"]}}}'
"""A structure file whose frontmatter schema forbids a block that holds `name`."""

REQUIRE_DESCRIPTION: Final[str] = '{"frontmatter": {"type": "object", "required": ["description"]}}'
"""A structure file whose frontmatter schema requires `description`."""

TEXT: Final[str] = dedent("""\
    ---
    name: setup
    ---
    # Setup
    """)
"""A document whose frontmatter holds one field, `name`, and no `description`."""

PROBLEM: Final[BlockProblem] = BlockProblem(
    "{'name': 'setup'} should not be valid under {'required': ['name']}",
    OtherBlockConstraint(),
    FieldCount(UnsignedInt(1)),
)
"""A constraint over the whole block broken: the rule's condition."""

LINE: Final[LineNumber] = LineNumber(NonZeroUnsignedInt(1))
"""The line a constraint over the whole block is reported on: it concerns no field."""


@pytest.mark.unit
class TestInvalidFrontmatter:
    def test_check_with_a_block_constraint_reports_it_on_line_1_naming_the_specification(self) -> None:
        #: Given
        subject = FakeDocumentContext(TEXT, corpus='guide', structure=FORBID_NAME)

        #: When
        occurrences = InvalidFrontmatter.check(subject)

        #: Then
        assert occurrences == (InvalidFrontmatter(source=CORPUS_SOURCE, line=LINE, problem=PROBLEM),), (
            "the block's one problem over the whole block is one occurrence, on line 1, naming the schema's "
            'specification'
        )

    def test_check_with_a_missing_field_reports_nothing(self) -> None:
        #: Given
        subject = FakeDocumentContext(TEXT, corpus='guide', structure=REQUIRE_DESCRIPTION)

        #: When
        occurrences = InvalidFrontmatter.check(subject)

        #: Then
        assert occurrences == (), "a required field missing, which concerns that field, is another rule's condition"

    def test_check_with_fewer_fields_than_min_properties_reports_nothing(self) -> None:
        #: Given
        structure = '{"frontmatter": {"type": "object", "minProperties": 2}}'
        subject = FakeDocumentContext(TEXT, corpus='guide', structure=structure)

        #: When
        occurrences = InvalidFrontmatter.check(subject)

        #: Then
        assert occurrences == (), "a block short of `minProperties` is `too-few-fields`'s condition"

    def test_check_with_more_fields_than_max_properties_reports_nothing(self) -> None:
        #: Given
        structure = '{"frontmatter": {"type": "object", "maxProperties": 0}}'
        subject = FakeDocumentContext(TEXT, corpus='guide', structure=structure)

        #: When
        occurrences = InvalidFrontmatter.check(subject)

        #: Then
        assert occurrences == (), "a block past `maxProperties` is `too-many-fields`'s condition"

    def test_check_with_two_schemas_reports_each_problem_with_its_own_specification(self) -> None:
        #: Given
        subject = FakeDocumentContext(
            TEXT,
            corpus='guide',
            structure=FORBID_NAME,
            namespaces=(namespace_spec('guide', 'setup', FORBID_NAME),),
        )

        #: When
        occurrences = InvalidFrontmatter.check(subject)

        #: Then
        assert occurrences == (
            InvalidFrontmatter(source=CORPUS_SOURCE, line=LINE, problem=PROBLEM),
            InvalidFrontmatter(source=NAMESPACE_SOURCE, line=LINE, problem=PROBLEM),
        ), 'each schema is applied on its own, so each reports the problem under its own specification, in order'

    def test_check_with_a_block_that_is_not_a_mapping_reports_nothing(self) -> None:
        #: Given
        text = dedent("""\
            ---
            - setup
            ---
            """)
        subject = FakeDocumentContext(text, corpus='guide', structure=FORBID_NAME)

        #: When
        occurrences = InvalidFrontmatter.check(subject)

        #: Then
        assert occurrences == (), (
            'no schema is applied to a block that is not a mapping, so it has no problem to report'
        )

    def test_check_with_a_described_schema_carries_its_description(self) -> None:
        #: Given
        structure = (
            '{"frontmatter": {"type": "object", "not": {"required": ["name"]}, '
            '"description": "The fields an agent lists a document by."}}'
        )
        subject = FakeDocumentContext(TEXT, corpus='guide', structure=structure)

        #: When
        occurrences = InvalidFrontmatter.check(subject)

        #: Then
        problem = BlockProblem(
            "{'name': 'setup'} should not be valid under {'required': ['name']}",
            OtherBlockConstraint(),
            FieldCount(UnsignedInt(1)),
            description='The fields an agent lists a document by.',
        )
        assert occurrences == (InvalidFrontmatter(source=CORPUS_SOURCE, line=LINE, problem=problem),), (
            "the root schema's description is carried with the problem"
        )

    def test_message_with_an_occurrence_states_the_constraint_on_the_whole_block(self) -> None:
        #: Given
        occurrence = InvalidFrontmatter(source=CORPUS_SOURCE, line=LINE, problem=PROBLEM)

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'frontmatter breaks a constraint of the schema on the whole block', (
            'the message states the condition, naming no specification and no keyword'
        )

    def test_labels_with_an_occurrence_label_nothing(self) -> None:
        #: Given
        occurrence = InvalidFrontmatter(source=CORPUS_SOURCE, line=LINE, problem=PROBLEM)

        #: When
        labels = occurrence.labels()

        #: Then
        assert labels == (), "a constraint with no typed limit has nothing to label but the validator's prose"

    def test_children_with_an_occurrence_end_with_the_validator_wording(self) -> None:
        #: Given
        occurrence = InvalidFrontmatter(source=CORPUS_SOURCE, line=LINE, problem=PROBLEM)

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note('the frontmatter schema is set here', at=Elsewhere(CORPUS_SPEC)),
            Note("{'name': 'setup'} should not be valid under {'required': ['name']}"),
        ), "the validator's wording is the only statement of the constraint"

    def test_children_with_a_description_give_it_as_the_help_before_the_validator_wording(self) -> None:
        #: Given
        problem = BlockProblem(
            'wrong',
            OtherBlockConstraint(),
            FieldCount(UnsignedInt(1)),
            description='The fields an agent lists a document by.',
        )
        occurrence = InvalidFrontmatter(source=CORPUS_SOURCE, line=LINE, problem=problem)

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note('the frontmatter schema is set here', at=Elsewhere(CORPUS_SPEC)),
            Help('The fields an agent lists a document by.'),
            Note('wrong'),
        ), 'the root schema description is shown as the schema wrote it'

    def test_children_with_the_agent_skills_specification_note_no_location(self) -> None:
        #: Given
        problem = BlockProblem('wrong', OtherBlockConstraint(), FieldCount(UnsignedInt(1)))
        occurrence = InvalidFrontmatter(source=AGENT_SKILLS_SOURCE, line=LINE, problem=problem)

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note("the Agent Skills specification states a SKILL.md's frontmatter schema"),
            Note('wrong'),
        ), 'the Agent Skills specification note has no location'
