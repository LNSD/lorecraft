"""`FM002`, `invalid-yaml`, over a document's or a skill's frontmatter.

Every case is a document or a `SKILL.md` written as text, read through a fake context that parses its frontmatter as
the real parser does; no file is read from disk.
"""

import sys
from textwrap import dedent
from typing import Final

import pytest

from lorecraft.core.num import NonZeroUnsignedInt
from lorecraft.core.path import PathComponent, RootRelativePath
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.context import DocumentFrontmatterOwner, SkillFrontmatterOwner
from lorecraft.project.syntax import LineNumber
from lorecraft.rules.location import Elsewhere, Help, Here, Label, Note
from lorecraft.rules.tests.fake_context import FakeDocumentContext, FakeSkillContext, structure_spec_path

from ..invalid_yaml import InvalidYaml

STRUCTURE: Final[str] = '{"frontmatter": {"type": "object"}}'
"""A corpus structure file whose frontmatter schema accepts any mapping."""

SPEC: Final[RootRelativePath] = structure_spec_path('guide')
"""Where the corpus structure file lies."""

DOCUMENT_OWNER: Final[DocumentFrontmatterOwner] = DocumentFrontmatterOwner(
    filename=AspectFilename.parse('setup'), spec=SPEC
)
"""The fake document, which the corpus structure file governs."""

SKILL_OWNER: Final[SkillFrontmatterOwner] = SkillFrontmatterOwner(
    directory_name=PathComponent.parse('review'), link_target=None
)
"""The fake skill, listed as `review` and not a link."""


def _stopped_at_line_3() -> InvalidYaml:
    """A document's occurrence for a block the YAML parser stopped reading on line 3."""
    return InvalidYaml(
        owner=DOCUMENT_OWNER,
        problem='mapping values are not allowed here',
        stopped_at=LineNumber(NonZeroUnsignedInt(3)),
    )


@pytest.mark.unit
class TestInvalidYaml:
    def test_check_with_a_block_that_is_not_yaml_reports_it_at_the_line_of_the_value(self) -> None:
        #: Given
        text = dedent("""\
            ---
            name: setup
            description: Setup: install the toolkit
            ---
            # Setup
            """)
        subject = FakeDocumentContext(text, corpus='guide', structure=STRUCTURE)

        #: When
        occurrences = InvalidYaml.check(subject)

        #: Then
        assert occurrences == (
            InvalidYaml(
                owner=DOCUMENT_OWNER,
                problem='this value holds `: `',
                stopped_at=LineNumber(NonZeroUnsignedInt(3)),
                help='Quote the value: `description: "Setup: install the toolkit"`',
            ),
        ), 'the occurrence is on the line of the value, with the words and the help of its kind'

    def test_check_with_no_line_known_reports_it_on_line_1(self) -> None:
        #: Given
        # reading spends at least one frame per level, so as many levels as the recursion limit always exhaust the
        # stack, and the parser can name no line
        depth = sys.getrecursionlimit()
        block = 'name: review\n' + ''.join(f'{" " * level}nested:\n' for level in range(depth)) + f'{" " * depth}a: b\n'
        subject = FakeSkillContext(f'---\n{block}---\n')

        #: When
        occurrences = InvalidYaml.check(subject)

        #: Then
        assert occurrences == (
            InvalidYaml(
                owner=SKILL_OWNER,
                problem='found collections nested too deeply to parse',
                stopped_at=None,
            ),
        ), 'a problem at no known line is reported on line 1; a skill under no specification file'

    def test_check_with_a_mapping_reports_nothing(self) -> None:
        #: Given
        text = dedent("""\
            ---
            name: setup
            ---
            # Setup
            """)
        subject = FakeDocumentContext(text, corpus='guide', structure=STRUCTURE)

        #: When
        occurrences = InvalidYaml.check(subject)

        #: Then
        assert occurrences == (), 'a block that reads as YAML is not invalid-yaml'

    def test_check_with_no_block_reports_nothing(self) -> None:
        #: Given
        subject = FakeSkillContext('# Review\n')

        #: When
        occurrences = InvalidYaml.check(subject)

        #: Then
        assert occurrences == (), 'a missing block is missing-frontmatter, never invalid-yaml'

    def test_message_with_an_occurrence_names_what_the_block_is_not(self) -> None:
        #: Given
        occurrence = _stopped_at_line_3()

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'frontmatter is not valid YAML', "the parser's words are the label's, so the message is fixed"

    def test_labels_with_a_known_line_carry_the_parser_problem_on_that_line(self) -> None:
        #: Given
        occurrence = _stopped_at_line_3()

        #: When
        labels = occurrence.labels()

        #: Then
        assert labels == (Label(Here(LineNumber(NonZeroUnsignedInt(3))), 'mapping values are not allowed here'),), (
            'the label sits on the line the parser stopped on and carries its words'
        )

    def test_construction_with_a_stopping_line_reports_at_that_line(self) -> None:
        #: Given
        stopped_at = LineNumber(NonZeroUnsignedInt(3))

        #: When
        occurrence = InvalidYaml(owner=DOCUMENT_OWNER, problem='found a problem', stopped_at=stopped_at)

        #: Then
        assert occurrence.line == stopped_at, 'the occurrence is reported on the line the reader stopped on'

    def test_construction_with_no_known_line_reports_at_line_1(self) -> None:
        #: Given
        stopped_at = None

        #: When
        occurrence = InvalidYaml(owner=DOCUMENT_OWNER, problem='found a problem', stopped_at=stopped_at)

        #: Then
        assert occurrence.line == LineNumber(NonZeroUnsignedInt(1)), 'the occurrence is reported where the block opens'

    def test_construction_with_a_line_of_its_own_is_refused(self) -> None:
        #: Given
        stopped_at = LineNumber(NonZeroUnsignedInt(3))

        #: When
        with pytest.raises(TypeError):
            InvalidYaml(
                owner=DOCUMENT_OWNER,
                line=LineNumber(NonZeroUnsignedInt(9)),  # ty: ignore[unknown-argument]
                problem='bad',
                stopped_at=stopped_at,
            )

        #: Then
        # the line is derived from `stopped_at`, so no caller can state one that disagrees with it

    def test_labels_with_no_known_line_say_the_problem_lies_in_the_block_opened_on_line_1(self) -> None:
        #: Given
        occurrence = InvalidYaml(owner=DOCUMENT_OWNER, problem='found a problem', stopped_at=None)

        #: When
        labels = occurrence.labels()

        #: Then
        assert labels == (
            Label(Here(LineNumber(NonZeroUnsignedInt(1))), 'found a problem, somewhere in the block opened here'),
        ), 'the label is on line 1, where the block opens, and says the line is not known'

    def test_children_with_a_document_point_at_its_specification(self) -> None:
        #: Given
        occurrence = _stopped_at_line_3()

        #: When
        children = occurrence.children()

        #: Then
        assert children == (Note('the frontmatter schema is set here', at=Elsewhere(SPEC)),), (
            'a note points at the specification that sets the schema'
        )

    def test_children_with_a_help_put_the_help_before_the_specification(self) -> None:
        #: Given
        occurrence = InvalidYaml(
            owner=DOCUMENT_OWNER,
            problem='this quote is never closed',
            stopped_at=LineNumber(NonZeroUnsignedInt(3)),
            help='Close it on the line it continues to, or remove it',
        )

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Help('Close it on the line it continues to, or remove it'),
            Note('the frontmatter schema is set here', at=Elsewhere(SPEC)),
        ), 'a syntax error names what to do about it before the specification that governs the block'

    def test_children_with_a_skill_name_the_agent_skills_specification(self) -> None:
        #: Given
        occurrence = InvalidYaml(
            owner=SKILL_OWNER,
            problem='mapping values are not allowed here',
            stopped_at=LineNumber(NonZeroUnsignedInt(3)),
        )

        #: When
        children = occurrence.children()

        #: Then
        assert children == (Note("the Agent Skills specification governs a SKILL.md's frontmatter"),), (
            'a note names the external specification, with no location'
        )
