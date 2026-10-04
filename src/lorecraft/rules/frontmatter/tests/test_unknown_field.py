"""`FM007`, `unknown-field`, over the problems the frontmatter schemas found.

The rule is pure, so every case here is a tuple of located problems; no frontmatter is read or validated.
"""

from typing import Final

import pytest

from lorecraft.core.path import RootRelativePath
from lorecraft.project.schemas import UnknownFieldProblem
from lorecraft.project.syntax import LineNumber
from lorecraft.rules.inputs import (
    AgentSkillsSchema,
    LocatedProblem,
    SchemaProblems,
    SchemaProblemsInput,
    StructureSpecSchema,
)
from lorecraft.rules.location import Elsewhere, Help, Note

from ..unknown_field import UnknownField

CORPUS_SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/guide.structure.json')
"""A corpus structure specification, which states a frontmatter schema."""

NAMESPACE_SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/guide-setup.structure.json')
"""A namespace structure specification under the same corpus, which states a frontmatter schema of its own."""

PROBLEM: Final[UnknownFieldProblem] = UnknownFieldProblem(
    'desc', "Additional properties are not allowed ('desc' was unexpected)"
)
"""A field the schema does not define: the rule's condition."""

LINE: Final[LineNumber] = LineNumber.from_int(3)
"""The line the builder placed `PROBLEM` on."""


def _document_input(*problems: LocatedProblem) -> SchemaProblemsInput:
    """The input of a document one corpus schema governs, which found the problems given.

    Args:
        problems: What the corpus schema found, each on its line.
    """
    return SchemaProblemsInput(
        schemas=(SchemaProblems(source=StructureSpecSchema(spec=CORPUS_SPEC), problems=problems),)
    )


@pytest.mark.unit
class TestUnknownField:
    def test_check_with_an_unknown_field_reports_it_on_its_line_naming_the_specification(self) -> None:
        #: Given
        subject = _document_input(LocatedProblem(problem=PROBLEM, line=LINE))

        #: When
        occurrences = UnknownField.check(subject)

        #: Then
        assert occurrences == (UnknownField(spec=CORPUS_SPEC, line=LINE, problem=PROBLEM),), (
            "one problem is one occurrence, on the line the builder placed it, naming the schema's specification"
        )

    def test_check_with_two_schemas_reports_each_problem_with_its_own_specification(self) -> None:
        #: Given
        located = LocatedProblem(problem=PROBLEM, line=LINE)
        subject = SchemaProblemsInput(
            schemas=(
                SchemaProblems(source=StructureSpecSchema(spec=CORPUS_SPEC), problems=(located,)),
                SchemaProblems(source=StructureSpecSchema(spec=NAMESPACE_SPEC), problems=(located,)),
            )
        )

        #: When
        occurrences = UnknownField.check(subject)

        #: Then
        assert occurrences == (
            UnknownField(spec=CORPUS_SPEC, line=LINE, problem=PROBLEM),
            UnknownField(spec=NAMESPACE_SPEC, line=LINE, problem=PROBLEM),
        ), 'each schema is applied on its own, so each reports the problem under its own specification, in order'

    def test_check_with_the_agent_skills_schema_reports_it_with_no_specification_file(self) -> None:
        #: Given
        subject = SchemaProblemsInput(
            schemas=(
                SchemaProblems(source=AgentSkillsSchema(), problems=(LocatedProblem(problem=PROBLEM, line=LINE),)),
            )
        )

        #: When
        occurrences = UnknownField.check(subject)

        #: Then
        assert occurrences == (UnknownField(spec=None, line=LINE, problem=PROBLEM),), (
            "the package states the Agent Skills schema, so a skill's occurrence names no specification file"
        )

    def test_check_with_no_schema_entry_reports_nothing(self) -> None:
        #: Given
        # the input of a frontmatter block that is not a mapping, which no schema was applied to
        subject = SchemaProblemsInput(schemas=())

        #: When
        occurrences = UnknownField.check(subject)

        #: Then
        assert occurrences == (), 'a block no schema was applied to has no problem to report'

    def test_message_with_an_occurrence_names_the_field(self) -> None:
        #: Given
        occurrence = UnknownField(spec=CORPUS_SPEC, line=LINE, problem=PROBLEM)

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'unknown field `desc`', (
            'the message names the field the schema does not define, in lowercase, naming no specification'
        )

    def test_children_with_a_document_occurrence_point_at_the_specification(self) -> None:
        #: Given
        occurrence = UnknownField(spec=CORPUS_SPEC, line=LINE, problem=PROBLEM)

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note('the frontmatter schema is set here', at=Elsewhere(CORPUS_SPEC)),
            Help('remove `desc`, or respell it as a field the schema defines'),
        ), 'a note points at where the schema is stated, and a help names the field to remove or respell'

    def test_children_with_a_skill_occurrence_name_the_agent_skills_specification(self) -> None:
        #: Given
        occurrence = UnknownField(spec=None, line=LINE, problem=PROBLEM)

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note("the Agent Skills specification states a SKILL.md's frontmatter schema"),
            Help('remove `desc`, or respell it as a field the schema defines'),
        ), 'the Agent Skills specification is no file, so its note has no location'
