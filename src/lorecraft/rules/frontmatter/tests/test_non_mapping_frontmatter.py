"""`FM003`, `non-mapping-frontmatter`, over a document's or a skill's frontmatter.

Every case is a document or a `SKILL.md` written as text, read through a fake context that parses its frontmatter as
the real parser does; no file is read from disk.
"""

from textwrap import dedent
from typing import Final

import pytest

from lorecraft.core.num import NonZeroUnsignedInt
from lorecraft.core.path import PathComponent, RootRelativePath
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.schemas import DocumentFrontmatterOwner, SkillFrontmatterOwner
from lorecraft.project.syntax import LineNumber
from lorecraft.rules.location import Elsewhere, Help, Note
from lorecraft.rules.tests.fake_database import FakeDocumentContext, FakeSkillContext, judged, structure_spec_path

from ..non_mapping_frontmatter import NonMappingFrontmatter

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


@pytest.mark.unit
class TestNonMappingFrontmatter:
    def test_check_with_a_document_whose_block_is_a_list_reports_it_on_line_1(self) -> None:
        #: Given
        text = dedent("""\
            ---
            - setup
            ---
            # Setup
            """)
        subject = FakeDocumentContext(text, corpus='guide', structure=STRUCTURE)

        #: When
        occurrences = judged(NonMappingFrontmatter, subject)

        #: Then
        assert occurrences == (NonMappingFrontmatter(owner=DOCUMENT_OWNER, line=LineNumber(NonZeroUnsignedInt(1))),), (
            'a block that is not a mapping is one occurrence, on line 1'
        )

    def test_check_with_an_empty_block_reports_it_on_line_1(self) -> None:
        #: Given
        text = dedent("""\
            ---
            ---
            # Setup
            """)
        subject = FakeDocumentContext(text, corpus='guide', structure=STRUCTURE)

        #: When
        occurrences = judged(NonMappingFrontmatter, subject)

        #: Then
        assert occurrences == (NonMappingFrontmatter(owner=DOCUMENT_OWNER, line=LineNumber(NonZeroUnsignedInt(1))),), (
            'an empty block holds no mapping, so it is not a mapping either'
        )

    def test_check_with_a_skill_whose_block_is_not_a_mapping_reports_it_under_no_specification_file(self) -> None:
        #: Given
        text = dedent("""\
            ---
            - review
            ---
            """)
        subject = FakeSkillContext(text)

        #: When
        occurrences = judged(NonMappingFrontmatter, subject)

        #: Then
        assert occurrences == (NonMappingFrontmatter(owner=SKILL_OWNER, line=LineNumber(NonZeroUnsignedInt(1))),), (
            'the package states the rule for a skill'
        )

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
        occurrences = judged(NonMappingFrontmatter, subject)

        #: Then
        assert occurrences == (), 'a mapping is what the rule asks for'

    def test_check_with_no_block_reports_nothing(self) -> None:
        #: Given
        subject = FakeDocumentContext('# Setup\n', corpus='guide', structure=STRUCTURE)

        #: When
        occurrences = judged(NonMappingFrontmatter, subject)

        #: Then
        assert occurrences == (), 'a missing block is missing-frontmatter, never non-mapping-frontmatter'

    def test_message_names_what_the_block_is_not(self) -> None:
        #: Given
        occurrence = NonMappingFrontmatter(owner=DOCUMENT_OWNER, line=LineNumber(NonZeroUnsignedInt(1)))

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'frontmatter is not a YAML mapping', 'the message names what the block is not'

    def test_children_with_a_document_point_at_its_specification_and_say_what_a_mapping_is(self) -> None:
        #: Given
        occurrence = NonMappingFrontmatter(owner=DOCUMENT_OWNER, line=LineNumber(NonZeroUnsignedInt(1)))

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note('the frontmatter schema is set here', at=Elsewhere(SPEC)),
            Help('write the block as `key: value` lines'),
        ), 'a note points at the specification that sets the schema, then a help says what a mapping looks like'

    def test_children_with_a_skill_name_the_agent_skills_specification(self) -> None:
        #: Given
        occurrence = NonMappingFrontmatter(owner=SKILL_OWNER, line=LineNumber(NonZeroUnsignedInt(1)))

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note("the Agent Skills specification governs a SKILL.md's frontmatter"),
            Help('write the block as `key: value` lines'),
        ), 'a note names the external specification, with no location, then the same help'
