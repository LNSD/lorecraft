"""`FM009`, `invalid-value`, over the problems the frontmatter schemas found.

The rule is pure, so every case here is a tuple of located problems; no frontmatter is read or validated.
"""

from typing import Final

import pytest

from lorecraft.core.path import RootRelativePath
from lorecraft.project.schemas import (
    InvalidValueProblem,
    WrongTypeProblem,
)
from lorecraft.project.syntax import LineNumber
from lorecraft.rules.inputs import (
    AgentSkillsSchema,
    LocatedProblem,
    SchemaProblems,
    SchemaProblemsInput,
    StructureSpecSchema,
)
from lorecraft.rules.location import Elsewhere, Note

from ..invalid_value import InvalidValue

CORPUS_SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/guide.structure.json')
"""A corpus structure specification, which states a frontmatter schema."""

NAMESPACE_SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/guide-setup.structure.json')
"""A namespace structure specification under the same corpus, which states a frontmatter schema of its own."""

PROBLEM: Final[InvalidValueProblem] = InvalidValueProblem('name', "'Setup Guide' does not match '^[a-z-]+$'")
"""A value breaking a pattern: the rule's condition."""

LINE: Final[LineNumber] = LineNumber.from_int(2)
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
class TestInvalidValue:
    def test_check_with_a_value_breaking_a_pattern_reports_it_on_its_line_naming_the_specification(self) -> None:
        #: Given
        subject = _document_input(LocatedProblem(problem=PROBLEM, line=LINE))

        #: When
        occurrences = InvalidValue.check(subject)

        #: Then
        assert occurrences == (InvalidValue(spec=CORPUS_SPEC, line=LINE, problem=PROBLEM),), (
            "one problem is one occurrence, on the line the builder placed it, naming the schema's specification"
        )

    def test_check_with_a_wrong_type_reports_nothing(self) -> None:
        #: Given
        subject = _document_input(
            LocatedProblem(problem=WrongTypeProblem('name', "3 is not of type 'string'"), line=LINE)
        )

        #: When
        occurrences = InvalidValue.check(subject)

        #: Then
        assert occurrences == (), "a value of the wrong type is another rule's condition"

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
        occurrences = InvalidValue.check(subject)

        #: Then
        assert occurrences == (
            InvalidValue(spec=CORPUS_SPEC, line=LINE, problem=PROBLEM),
            InvalidValue(spec=NAMESPACE_SPEC, line=LINE, problem=PROBLEM),
        ), 'each schema is applied on its own, so each reports the problem under its own specification, in order'

    def test_check_with_the_agent_skills_schema_reports_it_with_no_specification_file(self) -> None:
        #: Given
        subject = SchemaProblemsInput(
            schemas=(
                SchemaProblems(source=AgentSkillsSchema(), problems=(LocatedProblem(problem=PROBLEM, line=LINE),)),
            )
        )

        #: When
        occurrences = InvalidValue.check(subject)

        #: Then
        assert occurrences == (InvalidValue(spec=None, line=LINE, problem=PROBLEM),), (
            "the package states the Agent Skills schema, so a skill's occurrence names no specification file"
        )

    def test_check_with_no_schema_entry_reports_nothing(self) -> None:
        #: Given
        # the input of a frontmatter block that is not a mapping, which no schema was applied to
        subject = SchemaProblemsInput(schemas=())

        #: When
        occurrences = InvalidValue.check(subject)

        #: Then
        assert occurrences == (), 'a block no schema was applied to has no problem to report'

    def test_message_with_an_occurrence_names_the_field(self) -> None:
        #: Given
        occurrence = InvalidValue(spec=CORPUS_SPEC, line=LINE, problem=PROBLEM)

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'field `name` breaks a constraint of the schema', (
            'the message names the field, in lowercase, naming no specification'
        )

    def test_children_with_a_document_occurrence_point_at_the_specification(self) -> None:
        #: Given
        occurrence = InvalidValue(spec=CORPUS_SPEC, line=LINE, problem=PROBLEM)

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note(PROBLEM.message),
            Note('the frontmatter schema is set here', at=Elsewhere(CORPUS_SPEC)),
        ), "a note gives the schema's wording, then a note says where the schema is stated"

    def test_children_with_a_skill_occurrence_name_the_agent_skills_specification(self) -> None:
        #: Given
        occurrence = InvalidValue(spec=None, line=LINE, problem=PROBLEM)

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note(PROBLEM.message),
            Note("the Agent Skills specification states a SKILL.md's frontmatter schema"),
        ), 'the Agent Skills specification is no file, so its note has no location'
