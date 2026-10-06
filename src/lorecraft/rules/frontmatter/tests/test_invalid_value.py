"""`FM009`, `invalid-value`, over the problems the frontmatter schemas find in a subject's frontmatter.

Every case is a document or a `SKILL.md` written as text, read through a fake context that holds it to its schemas as
the real analysis does, under structure specifications decoded from JSON; no file is read from disk.
"""

from typing import Final

import pytest

from lorecraft.core.path import RootRelativePath
from lorecraft.project.schemas import InvalidValueProblem
from lorecraft.project.syntax import LineNumber
from lorecraft.rules.location import Elsewhere, Note
from lorecraft.rules.tests.fake_context import (
    FakeDocumentContext,
    FakeSkillContext,
    namespace_spec,
    structure_spec_path,
)

from ..invalid_value import InvalidValue

CORPUS_SPEC: Final[RootRelativePath] = structure_spec_path('guide')
"""Where the corpus structure specification lies."""

NAMESPACE_SPEC: Final[RootRelativePath] = structure_spec_path('guide-setup')
"""Where a namespace structure specification under the same corpus lies."""

NAME_PATTERN: Final[str] = (
    '{"frontmatter": {"type": "object", "properties": {"name": {"type": "string", "pattern": "^[a-z-]+$"}}}}'
)
"""A structure specification whose frontmatter schema holds `name` to a string of lowercase letters and hyphens."""

TEXT: Final[str] = '---\nname: Setup Guide\n---\n# Setup\n'
"""A document whose `name`, on line 2, breaks the pattern."""

PROBLEM: Final[InvalidValueProblem] = InvalidValueProblem('name', "'Setup Guide' does not match '^[a-z-]+$'")
"""A value breaking a pattern: the rule's condition."""

LINE: Final[LineNumber] = LineNumber.from_int(2)
"""The line `name` is written on."""


@pytest.mark.unit
class TestInvalidValue:
    def test_check_with_a_value_breaking_a_pattern_reports_it_on_its_line_naming_the_specification(self) -> None:
        #: Given
        subject = FakeDocumentContext(TEXT, corpus='guide', structure=NAME_PATTERN)

        #: When
        occurrences = InvalidValue.check(subject)

        #: Then
        assert occurrences == (InvalidValue(spec=CORPUS_SPEC, line=LINE, problem=PROBLEM),), (
            "one problem is one occurrence, on the line its field is written on, naming the schema's specification"
        )

    def test_check_with_a_wrong_type_reports_nothing(self) -> None:
        #: Given
        subject = FakeDocumentContext('---\nname: 3\n---\n', corpus='guide', structure=NAME_PATTERN)

        #: When
        occurrences = InvalidValue.check(subject)

        #: Then
        assert occurrences == (), "a value of the wrong type is another rule's condition"

    def test_check_with_two_schemas_reports_each_problem_with_its_own_specification(self) -> None:
        #: Given
        subject = FakeDocumentContext(
            TEXT, corpus='guide', structure=NAME_PATTERN, namespaces=(namespace_spec('guide', 'setup', NAME_PATTERN),)
        )

        #: When
        occurrences = InvalidValue.check(subject)

        #: Then
        assert occurrences == (
            InvalidValue(spec=CORPUS_SPEC, line=LINE, problem=PROBLEM),
            InvalidValue(spec=NAMESPACE_SPEC, line=LINE, problem=PROBLEM),
        ), 'each schema is applied on its own, so each reports the problem under its own specification, in order'

    def test_check_with_a_skill_reports_it_with_no_specification_file(self) -> None:
        #: Given
        subject = FakeSkillContext('---\nname: review\ndescription: Review a change.\ncompatibility: ""\n---\n')

        #: When
        occurrences = InvalidValue.check(subject)

        #: Then
        problem = InvalidValueProblem(
            'compatibility', 'skill compatibility cannot be empty; leave the field out instead'
        )
        assert occurrences == (InvalidValue(spec=None, line=LineNumber.from_int(4), problem=problem),), (
            "the package states the Agent Skills schema, so a skill's occurrence names no specification file"
        )

    def test_check_with_a_block_that_is_not_a_mapping_reports_nothing(self) -> None:
        #: Given
        subject = FakeDocumentContext('---\n- Setup Guide\n---\n', corpus='guide', structure=NAME_PATTERN)

        #: When
        occurrences = InvalidValue.check(subject)

        #: Then
        assert occurrences == (), (
            'no schema is applied to a block that is not a mapping, so it has no problem to report'
        )

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
