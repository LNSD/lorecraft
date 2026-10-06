"""`FM006`, `missing-field`, over the problems the frontmatter schemas find in a subject's frontmatter.

Every case is a document or a `SKILL.md` written as text, read through a fake context that holds it to its schemas as
the real analysis does, under structure specifications decoded from JSON; no file is read from disk.
"""

from typing import Final

import pytest

from lorecraft.core.path import RootRelativePath
from lorecraft.project.schemas import MissingFieldProblem
from lorecraft.project.syntax import LineNumber
from lorecraft.rules.location import Elsewhere, Help, Note
from lorecraft.rules.tests.fake_context import (
    FakeDocumentContext,
    FakeSkillContext,
    namespace_spec,
    structure_spec_path,
)

from ..missing_field import MissingField

CORPUS_SPEC: Final[RootRelativePath] = structure_spec_path('guide')
"""Where the corpus structure specification lies."""

NAMESPACE_SPEC: Final[RootRelativePath] = structure_spec_path('guide-setup')
"""Where a namespace structure specification under the same corpus lies."""

REQUIRE_DESCRIPTION: Final[str] = '{"frontmatter": {"type": "object", "required": ["description"]}}'
"""A structure specification whose frontmatter schema requires `description`."""

CLOSED: Final[str] = '{"frontmatter": {"type": "object", "properties": {"name": {}}, "additionalProperties": false}}'
"""A structure specification whose frontmatter schema defines `name` and no other field."""

TEXT: Final[str] = '---\nname: setup\n---\n# Setup\n'
"""A document whose frontmatter lacks `description`."""

PROBLEM: Final[MissingFieldProblem] = MissingFieldProblem('description', "'description' is a required property")
"""A required field missing: the rule's condition."""

LINE: Final[LineNumber] = LineNumber.from_int(1)
"""The line a missing field is reported on: it is written on none."""


@pytest.mark.unit
class TestMissingField:
    def test_check_with_a_missing_field_reports_it_on_line_1_naming_the_specification(self) -> None:
        #: Given
        subject = FakeDocumentContext(TEXT, corpus='guide', structure=REQUIRE_DESCRIPTION)

        #: When
        occurrences = MissingField.check(subject)

        #: Then
        assert occurrences == (MissingField(spec=CORPUS_SPEC, line=LINE, problem=PROBLEM),), (
            "one problem is one occurrence, on line 1, since the field is written on none, naming the schema's "
            'specification'
        )

    def test_check_with_an_unknown_field_reports_nothing(self) -> None:
        #: Given
        subject = FakeDocumentContext('---\nname: setup\ndesc: Install.\n---\n', corpus='guide', structure=CLOSED)

        #: When
        occurrences = MissingField.check(subject)

        #: Then
        assert occurrences == (), "a field the schema does not define is another rule's condition"

    def test_check_with_two_schemas_reports_each_problem_with_its_own_specification(self) -> None:
        #: Given
        subject = FakeDocumentContext(
            TEXT,
            corpus='guide',
            structure=REQUIRE_DESCRIPTION,
            namespaces=(namespace_spec('guide', 'setup', REQUIRE_DESCRIPTION),),
        )

        #: When
        occurrences = MissingField.check(subject)

        #: Then
        assert occurrences == (
            MissingField(spec=CORPUS_SPEC, line=LINE, problem=PROBLEM),
            MissingField(spec=NAMESPACE_SPEC, line=LINE, problem=PROBLEM),
        ), 'each schema is applied on its own, so each reports the problem under its own specification, in order'

    def test_check_with_a_skill_reports_it_with_no_specification_file(self) -> None:
        #: Given
        subject = FakeSkillContext('---\nname: review\n---\n')

        #: When
        occurrences = MissingField.check(subject)

        #: Then
        assert occurrences == (
            MissingField(spec=None, line=LINE, problem=MissingFieldProblem('description', '`description` is required')),
        ), "the package states the Agent Skills schema, so a skill's occurrence names no specification file"

    def test_check_with_a_block_that_is_not_a_mapping_reports_nothing(self) -> None:
        #: Given
        subject = FakeDocumentContext('---\n- setup\n---\n', corpus='guide', structure=REQUIRE_DESCRIPTION)

        #: When
        occurrences = MissingField.check(subject)

        #: Then
        assert occurrences == (), (
            'no schema is applied to a block that is not a mapping, so it has no problem to report'
        )

    def test_message_with_an_occurrence_names_the_field(self) -> None:
        #: Given
        occurrence = MissingField(spec=CORPUS_SPEC, line=LINE, problem=PROBLEM)

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'missing required field `description`', (
            'the message names the missing field, in lowercase, naming no specification'
        )

    def test_children_with_a_document_occurrence_point_at_the_specification(self) -> None:
        #: Given
        occurrence = MissingField(spec=CORPUS_SPEC, line=LINE, problem=PROBLEM)

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note('the frontmatter schema is set here', at=Elsewhere(CORPUS_SPEC)),
            Help('add `description` to the frontmatter'),
        ), 'a note points at where the schema is stated, and a help names the field to add'

    def test_children_with_a_skill_occurrence_name_the_agent_skills_specification(self) -> None:
        #: Given
        occurrence = MissingField(spec=None, line=LINE, problem=PROBLEM)

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note("the Agent Skills specification states a SKILL.md's frontmatter schema"),
            Help('add `description` to the frontmatter'),
        ), 'the Agent Skills specification is no file, so its note has no location'
