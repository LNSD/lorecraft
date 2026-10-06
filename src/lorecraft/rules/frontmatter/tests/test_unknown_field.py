"""`FM007`, `unknown-field`, over the problems the frontmatter schemas find in a subject's frontmatter.

Every case is a document or a `SKILL.md` written as text, read through a fake context that holds it to its schemas as
the real analysis does, under structure specifications decoded from JSON; no file is read from disk.
"""

from typing import Final

import pytest

from lorecraft.core.path import RootRelativePath
from lorecraft.project.schemas import UnknownFieldProblem
from lorecraft.project.syntax import LineNumber
from lorecraft.rules.location import Elsewhere, Help, Note
from lorecraft.rules.tests.fake_context import (
    FakeDocumentContext,
    FakeSkillContext,
    namespace_spec,
    structure_spec_path,
)

from ..unknown_field import UnknownField

CORPUS_SPEC: Final[RootRelativePath] = structure_spec_path('guide')
"""Where the corpus structure specification lies."""

NAMESPACE_SPEC: Final[RootRelativePath] = structure_spec_path('guide-setup')
"""Where a namespace structure specification under the same corpus lies."""

CLOSED: Final[str] = (
    '{"frontmatter": {"type": "object", "properties": {"name": {}, "description": {}}, "additionalProperties": false}}'
)
"""A structure specification whose frontmatter schema defines `name` and `description`, and no other field."""

REQUIRE_DESCRIPTION: Final[str] = '{"frontmatter": {"type": "object", "required": ["description"]}}'
"""A structure specification whose frontmatter schema requires `description`."""

TEXT: Final[str] = '---\nname: setup\ndescription: Install.\ndesc: Install it.\n---\n# Setup\n'
"""A document whose frontmatter writes `desc`, on line 4."""

PROBLEM: Final[UnknownFieldProblem] = UnknownFieldProblem(
    'desc', "Additional properties are not allowed ('desc' was unexpected)"
)
"""A field the schema does not define: the rule's condition."""

LINE: Final[LineNumber] = LineNumber.from_int(4)
"""The line `desc` is written on."""


@pytest.mark.unit
class TestUnknownField:
    def test_check_with_an_unknown_field_reports_it_on_its_line_naming_the_specification(self) -> None:
        #: Given
        subject = FakeDocumentContext(TEXT, corpus='guide', structure=CLOSED)

        #: When
        occurrences = UnknownField.check(subject)

        #: Then
        assert occurrences == (UnknownField(spec=CORPUS_SPEC, line=LINE, problem=PROBLEM),), (
            "one problem is one occurrence, on the line its field is written on, naming the schema's specification"
        )

    def test_check_with_a_missing_field_reports_nothing(self) -> None:
        #: Given
        subject = FakeDocumentContext('---\nname: setup\n---\n', corpus='guide', structure=REQUIRE_DESCRIPTION)

        #: When
        occurrences = UnknownField.check(subject)

        #: Then
        assert occurrences == (), "a required field missing is another rule's condition"

    def test_check_with_two_schemas_reports_each_problem_with_its_own_specification(self) -> None:
        #: Given
        subject = FakeDocumentContext(
            TEXT, corpus='guide', structure=CLOSED, namespaces=(namespace_spec('guide', 'setup', CLOSED),)
        )

        #: When
        occurrences = UnknownField.check(subject)

        #: Then
        assert occurrences == (
            UnknownField(spec=CORPUS_SPEC, line=LINE, problem=PROBLEM),
            UnknownField(spec=NAMESPACE_SPEC, line=LINE, problem=PROBLEM),
        ), 'each schema is applied on its own, so each reports the problem under its own specification, in order'

    def test_check_with_a_skill_reports_it_with_no_specification_file(self) -> None:
        #: Given
        subject = FakeSkillContext('---\nname: review\ndescription: Review a change.\ndesc: Review it.\n---\n')

        #: When
        occurrences = UnknownField.check(subject)

        #: Then
        problem = UnknownFieldProblem('desc', '`desc` is not a field of the Agent Skills specification')
        assert occurrences == (UnknownField(spec=None, line=LINE, problem=problem),), (
            "the package states the Agent Skills schema, so a skill's occurrence names no specification file"
        )

    def test_check_with_a_block_that_is_not_a_mapping_reports_nothing(self) -> None:
        #: Given
        subject = FakeDocumentContext('---\n- desc\n---\n', corpus='guide', structure=CLOSED)

        #: When
        occurrences = UnknownField.check(subject)

        #: Then
        assert occurrences == (), (
            'no schema is applied to a block that is not a mapping, so it has no problem to report'
        )

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
