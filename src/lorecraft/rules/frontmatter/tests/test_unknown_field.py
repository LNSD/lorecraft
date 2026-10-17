"""`FM007`, `unknown-field`, over the problems the frontmatter schemas find in a subject's frontmatter.

Every case is a document or a `SKILL.md` written as text, read through a fake context that holds it to its schemas as
the real analysis does, under structure files decoded from JSON; no file is read from disk.
"""

from textwrap import dedent
from typing import Final

import pytest

from lorecraft.core.num import NonZeroUnsignedInt
from lorecraft.core.path import RootRelativePath
from lorecraft.project.schemas import AgentSkillsSchema, StructureSpecSchema, UnknownFieldProblem
from lorecraft.project.syntax import LineNumber
from lorecraft.rules.location import Elsewhere, Help, Here, Label, Note
from lorecraft.rules.tests.fake_database import (
    FakeDocumentDatabase,
    FakeSkillDatabase,
    judged,
    namespace_spec,
    structure_spec_path,
)

from ..unknown_field import UnknownField

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

CLOSED: Final[str] = (
    '{"frontmatter": {"type": "object", "properties": {"name": {}, "description": {}}, "additionalProperties": false}}'
)
"""A structure file whose frontmatter schema defines `name` and `description`, and no other field."""

REQUIRE_DESCRIPTION: Final[str] = '{"frontmatter": {"type": "object", "required": ["description"]}}'
"""A structure file whose frontmatter schema requires `description`."""

TEXT: Final[str] = dedent("""\
    ---
    name: setup
    description: Install.
    desc: Install it.
    ---
    # Setup
    """)
"""A document whose frontmatter writes `desc`, on line 4."""

PROBLEM: Final[UnknownFieldProblem] = UnknownFieldProblem(
    'desc', "Additional properties are not allowed ('desc' was unexpected)", known_fields=('name', 'description')
)
"""A field the schema does not define: the rule's condition."""

LINE: Final[LineNumber] = LineNumber(NonZeroUnsignedInt(4))
"""The line `desc` is written on."""


@pytest.mark.unit
class TestUnknownField:
    def test_check_with_an_unknown_field_reports_it_on_its_line_naming_the_specification(self) -> None:
        #: Given
        subject = FakeDocumentDatabase(TEXT, corpus='guide', structure=CLOSED)

        #: When
        occurrences = judged(UnknownField, subject)

        #: Then
        assert occurrences == (UnknownField(source=CORPUS_SOURCE, line=LINE, problem=PROBLEM),), (
            "one problem is one occurrence, on the line its field is written on, naming the schema's specification"
        )

    def test_check_with_a_missing_field_reports_nothing(self) -> None:
        #: Given
        text = dedent("""\
            ---
            name: setup
            ---
            """)
        subject = FakeDocumentDatabase(text, corpus='guide', structure=REQUIRE_DESCRIPTION)

        #: When
        occurrences = judged(UnknownField, subject)

        #: Then
        assert occurrences == (), "a required field missing is another rule's condition"

    def test_check_with_two_schemas_reports_each_problem_with_its_own_specification(self) -> None:
        #: Given
        subject = FakeDocumentDatabase(
            TEXT, corpus='guide', structure=CLOSED, namespaces=(namespace_spec('guide', 'setup', CLOSED),)
        )

        #: When
        occurrences = judged(UnknownField, subject)

        #: Then
        assert occurrences == (
            UnknownField(source=CORPUS_SOURCE, line=LINE, problem=PROBLEM),
            UnknownField(source=NAMESPACE_SOURCE, line=LINE, problem=PROBLEM),
        ), 'each schema is applied on its own, so each reports the problem under its own specification, in order'

    def test_check_with_a_skill_reports_it_with_no_specification_file(self) -> None:
        #: Given
        text = dedent("""\
            ---
            name: review
            description: Review a change.
            desc: Review it.
            ---
            """)
        subject = FakeSkillDatabase(text)

        #: When
        occurrences = judged(UnknownField, subject)

        #: Then
        problem = UnknownFieldProblem(
            'desc',
            '`desc` is not a field of the Agent Skills specification',
            known_fields=('name', 'description', 'license', 'compatibility', 'metadata', 'allowed-tools'),
        )
        assert occurrences == (UnknownField(source=AGENT_SKILLS_SOURCE, line=LINE, problem=problem),), (
            "the package states the Agent Skills schema, so a skill's occurrence names no specification file"
        )

    def test_check_with_a_block_that_is_not_a_mapping_reports_nothing(self) -> None:
        #: Given
        text = dedent("""\
            ---
            - desc
            ---
            """)
        subject = FakeDocumentDatabase(text, corpus='guide', structure=CLOSED)

        #: When
        occurrences = judged(UnknownField, subject)

        #: Then
        assert occurrences == (), (
            'no schema is applied to a block that is not a mapping, so it has no problem to report'
        )

    def test_message_names_the_field(self) -> None:
        #: Given
        occurrence = UnknownField(source=CORPUS_SOURCE, line=LINE, problem=PROBLEM)

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'unknown field `desc`', (
            'the message names the field the schema does not define, in lowercase, naming no specification'
        )

    def test_children_with_a_document_occurrence_point_at_the_specification(self) -> None:
        #: Given
        occurrence = UnknownField(source=CORPUS_SOURCE, line=LINE, problem=PROBLEM)

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note('the frontmatter schema is set here', at=Elsewhere(CORPUS_SPEC)),
            Help('remove `desc`, or respell it as a field the schema defines'),
            Note('the schema defines: `name`, `description`'),
        ), 'a note points at where the schema is stated, a help names the field to remove or respell, a note the fields'

    def test_children_with_a_skill_occurrence_name_the_agent_skills_specification(self) -> None:
        #: Given
        occurrence = UnknownField(source=AGENT_SKILLS_SOURCE, line=LINE, problem=PROBLEM)

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note("the Agent Skills specification states a SKILL.md's frontmatter schema"),
            Help('remove `desc`, or respell it as a field the schema defines'),
            Note('the schema defines: `name`, `description`'),
        ), 'the Agent Skills specification is no file, so its note has no location'

    def test_children_with_a_schema_that_names_no_field_list_none(self) -> None:
        #: Given
        problem = UnknownFieldProblem('desc', 'Unevaluated properties are not allowed', known_fields=())
        occurrence = UnknownField(source=CORPUS_SOURCE, line=LINE, problem=problem)

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note('the frontmatter schema is set here', at=Elsewhere(CORPUS_SPEC)),
            Help('remove `desc`, or respell it as a field the schema defines'),
        ), 'a schema whose own properties name no field has no list to give, as when it composes others'

    def test_labels_say_the_schema_does_not_define_the_field(self) -> None:
        #: Given
        occurrence = UnknownField(source=CORPUS_SOURCE, line=LINE, problem=PROBLEM)

        #: When
        labels = occurrence.labels()

        #: Then
        assert labels == (Label(Here(LINE), 'not defined by the schema'),), 'the label is on the field line'
