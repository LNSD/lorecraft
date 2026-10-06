"""`FM010`, `block-constraint`, over the problems the frontmatter schemas find in a subject's frontmatter.

Every case is a document or a `SKILL.md` written as text, read through a fake context that holds it to its schemas as
the real analysis does, under structure specifications decoded from JSON; no file is read from disk.

No skill appears here: the Agent Skills specification places every problem it finds on a field, so a skill's
frontmatter breaks no constraint over the whole block, and the note such an occurrence would carry is tested on its
own below.
"""

from typing import Final

import pytest

from lorecraft.core.path import RootRelativePath
from lorecraft.project.schemas import BlockProblem
from lorecraft.project.syntax import LineNumber
from lorecraft.rules.location import Elsewhere, Note
from lorecraft.rules.tests.fake_context import FakeDocumentContext, namespace_spec, structure_spec_path

from ..block_constraint import BlockConstraint

CORPUS_SPEC: Final[RootRelativePath] = structure_spec_path('guide')
"""Where the corpus structure specification lies."""

NAMESPACE_SPEC: Final[RootRelativePath] = structure_spec_path('guide-setup')
"""Where a namespace structure specification under the same corpus lies."""

MIN_PROPERTIES: Final[str] = '{"frontmatter": {"type": "object", "required": ["description"], "minProperties": 2}}'
"""A structure specification whose frontmatter schema requires `description` and at least two fields."""

REQUIRE_DESCRIPTION: Final[str] = '{"frontmatter": {"type": "object", "required": ["description"]}}'
"""A structure specification whose frontmatter schema requires `description`."""

TEXT: Final[str] = '---\nname: setup\n---\n# Setup\n'
"""A document whose frontmatter holds one field, and no `description`."""

PROBLEM: Final[BlockProblem] = BlockProblem("{'name': 'setup'} does not have enough properties")
"""A constraint over the whole block broken: the rule's condition."""

LINE: Final[LineNumber] = LineNumber.from_int(1)
"""The line a constraint over the whole block is reported on: it concerns no field."""


@pytest.mark.unit
class TestBlockConstraint:
    def test_check_with_a_block_constraint_reports_it_on_line_1_naming_the_specification(self) -> None:
        #: Given
        subject = FakeDocumentContext(TEXT, corpus='guide', structure=MIN_PROPERTIES)

        #: When
        occurrences = BlockConstraint.check(subject)

        #: Then
        assert occurrences == (BlockConstraint(spec=CORPUS_SPEC, line=LINE, problem=PROBLEM),), (
            "the block's one problem over the whole block is one occurrence, on line 1, naming the schema's "
            'specification; the missing field the schema also finds is left to its own rule'
        )

    def test_check_with_a_missing_field_reports_nothing(self) -> None:
        #: Given
        subject = FakeDocumentContext(TEXT, corpus='guide', structure=REQUIRE_DESCRIPTION)

        #: When
        occurrences = BlockConstraint.check(subject)

        #: Then
        assert occurrences == (), "a required field missing, which concerns that field, is another rule's condition"

    def test_check_with_two_schemas_reports_each_problem_with_its_own_specification(self) -> None:
        #: Given
        subject = FakeDocumentContext(
            TEXT,
            corpus='guide',
            structure=MIN_PROPERTIES,
            namespaces=(namespace_spec('guide', 'setup', MIN_PROPERTIES),),
        )

        #: When
        occurrences = BlockConstraint.check(subject)

        #: Then
        assert occurrences == (
            BlockConstraint(spec=CORPUS_SPEC, line=LINE, problem=PROBLEM),
            BlockConstraint(spec=NAMESPACE_SPEC, line=LINE, problem=PROBLEM),
        ), 'each schema is applied on its own, so each reports the problem under its own specification, in order'

    def test_check_with_a_block_that_is_not_a_mapping_reports_nothing(self) -> None:
        #: Given
        subject = FakeDocumentContext('---\n- setup\n---\n', corpus='guide', structure=MIN_PROPERTIES)

        #: When
        occurrences = BlockConstraint.check(subject)

        #: Then
        assert occurrences == (), (
            'no schema is applied to a block that is not a mapping, so it has no problem to report'
        )

    def test_message_with_an_occurrence_states_the_condition(self) -> None:
        #: Given
        occurrence = BlockConstraint(spec=CORPUS_SPEC, line=LINE, problem=PROBLEM)

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'frontmatter breaks a constraint of the schema on the whole block', (
            'the message states the condition, in lowercase, naming no specification'
        )

    def test_children_with_a_document_occurrence_point_at_the_specification(self) -> None:
        #: Given
        occurrence = BlockConstraint(spec=CORPUS_SPEC, line=LINE, problem=PROBLEM)

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note(PROBLEM.message),
            Note('the frontmatter schema is set here', at=Elsewhere(CORPUS_SPEC)),
        ), "a note gives the schema's wording, then a note says where the schema is stated"

    def test_children_with_a_skill_occurrence_name_the_agent_skills_specification(self) -> None:
        #: Given
        occurrence = BlockConstraint(spec=None, line=LINE, problem=PROBLEM)

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note(PROBLEM.message),
            Note("the Agent Skills specification states a SKILL.md's frontmatter schema"),
        ), 'the Agent Skills specification is no file, so its note has no location'
