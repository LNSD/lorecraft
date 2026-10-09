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
from lorecraft.project.schemas import BlockProblem, MaxFields, MinFields, OtherBlockConstraint
from lorecraft.project.syntax import LineNumber
from lorecraft.rules.location import Elsewhere, Help, Here, Label, Note
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

PROBLEM: Final[BlockProblem] = BlockProblem("{'name': 'setup'} does not have enough properties", MinFields(2), 1)
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
        assert message == 'frontmatter has the wrong number of fields (1; at least 2)', (
            'the message states the condition and the number found against the limit, naming no specification'
        )

    def test_message_with_too_many_fields_says_the_most_allowed(self) -> None:
        #: Given
        problem = BlockProblem('too many', MaxFields(1), 3)
        occurrence = BlockConstraint(spec=CORPUS_SPEC, line=LINE, problem=problem)

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'frontmatter has the wrong number of fields (3; at most 1)', (
            'the same template is filled with the maximum'
        )

    def test_message_with_another_keyword_states_the_constraint_on_the_whole_block(self) -> None:
        #: Given
        problem = BlockProblem('wrong', OtherBlockConstraint(), 1)
        occurrence = BlockConstraint(spec=CORPUS_SPEC, line=LINE, problem=problem)

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'frontmatter breaks a constraint of the schema on the whole block', (
            'a keyword with no typed limit has no count to state'
        )

    def test_check_with_a_described_schema_carries_its_description(self) -> None:
        #: Given
        structure = (
            '{"frontmatter": {"type": "object", "minProperties": 2, '
            '"description": "The fields an agent lists a document by."}}'
        )
        subject = FakeDocumentContext(TEXT, corpus='guide', structure=structure)

        #: When
        occurrences = BlockConstraint.check(subject)

        #: Then
        problem = BlockProblem(
            "{'name': 'setup'} does not have enough properties",
            MinFields(2),
            1,
            description='The fields an agent lists a document by.',
        )
        assert occurrences == (BlockConstraint(spec=CORPUS_SPEC, line=LINE, problem=problem),), (
            "the root schema's description is carried with the limit and the number of fields"
        )

    def test_labels_with_a_limit_on_the_fields_name_what_is_out_of_limit_on_line_1(self) -> None:
        #: Given
        occurrence = BlockConstraint(spec=CORPUS_SPEC, line=LINE, problem=PROBLEM)

        #: When
        labels = occurrence.labels()

        #: Then
        assert labels == (Label(Here(LINE), 'number of fields'),), (
            'the label is on line 1, the whole block, and carries no number: the message has it'
        )

    def test_labels_with_another_keyword_label_nothing(self) -> None:
        #: Given
        problem = BlockProblem('wrong', OtherBlockConstraint(), 1)
        occurrence = BlockConstraint(spec=CORPUS_SPEC, line=LINE, problem=problem)

        #: When
        labels = occurrence.labels()

        #: Then
        assert labels == (), "a keyword with no typed constraint has nothing to label but the validator's prose"

    def test_children_with_a_limit_on_the_number_of_fields_point_at_the_specification_only(self) -> None:
        #: Given
        occurrence = BlockConstraint(spec=CORPUS_SPEC, line=LINE, problem=PROBLEM)

        #: When
        children = occurrence.children()

        #: Then
        assert children == (Note('the frontmatter schema is set here', at=Elsewhere(CORPUS_SPEC)),), (
            "the message states the limit, whose prose would repeat the block's whole frontmatter"
        )

    def test_children_with_a_description_give_it_as_the_help(self) -> None:
        #: Given
        problem = BlockProblem('too few', MinFields(2), 1, description='The fields an agent lists a document by.')
        occurrence = BlockConstraint(spec=CORPUS_SPEC, line=LINE, problem=problem)

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note('the frontmatter schema is set here', at=Elsewhere(CORPUS_SPEC)),
            Help('The fields an agent lists a document by.'),
        ), 'the root schema description is shown as the schema wrote it'

    def test_children_with_another_keyword_end_with_the_validator_wording(self) -> None:
        #: Given
        problem = BlockProblem('wrong', OtherBlockConstraint(), 1)
        occurrence = BlockConstraint(spec=None, line=LINE, problem=problem)

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note("the Agent Skills specification states a SKILL.md's frontmatter schema"),
            Note('wrong'),
        ), "the validator's wording is the fallback, and the Agent Skills specification note has no location"
