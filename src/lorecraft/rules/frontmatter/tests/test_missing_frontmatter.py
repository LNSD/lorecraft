"""`LC201`, `missing-frontmatter`, over a document's or a skill's frontmatter.

Every case is a document or a skill entrypoint (`SKILL.md`) written as text, read through a fake database that
parses its frontmatter as
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
from lorecraft.rules.location import Elsewhere, Help, Here, Label, Note
from lorecraft.rules.tests.fake_database import FakeDocumentDatabase, FakeSkillDatabase, judged, structure_spec_path

from ..missing_frontmatter import MissingFrontmatter

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
class TestMissingFrontmatter:
    def test_check_with_a_document_without_a_block_reports_it_on_line_1(self) -> None:
        #: Given
        subject = FakeDocumentDatabase('# Setup\n', corpus='guide', structure=STRUCTURE)

        #: When
        occurrences = judged(MissingFrontmatter, subject)

        #: Then
        assert occurrences == (MissingFrontmatter(owner=DOCUMENT_OWNER, line=LineNumber(NonZeroUnsignedInt(1))),), (
            "a document with no block is one occurrence, on line 1, under its corpus's specification"
        )

    def test_check_with_a_block_never_closed_reports_it_on_line_1(self) -> None:
        #: Given
        text = dedent("""\
            ---
            name: setup
            # Setup
            """)
        subject = FakeDocumentDatabase(text, corpus='guide', structure=STRUCTURE)

        #: When
        occurrences = judged(MissingFrontmatter, subject)

        #: Then
        assert occurrences == (MissingFrontmatter(owner=DOCUMENT_OWNER, line=LineNumber(NonZeroUnsignedInt(1))),), (
            'a block no second `---` line closes is no block at all'
        )

    def test_check_with_a_skill_without_a_block_reports_it_under_no_specification_file(self) -> None:
        #: Given
        subject = FakeSkillDatabase('# Review\n', directory_name='review')

        #: When
        occurrences = judged(MissingFrontmatter, subject)

        #: Then
        assert occurrences == (MissingFrontmatter(owner=SKILL_OWNER, line=LineNumber(NonZeroUnsignedInt(1))),), (
            'the package states the rule for a skill, after the Agent Skills specification'
        )

    def test_check_with_a_block_that_is_not_yaml_reports_nothing(self) -> None:
        #: Given
        text = dedent("""\
            ---
            name: [setup
            ---
            # Setup
            """)
        subject = FakeDocumentDatabase(text, corpus='guide', structure=STRUCTURE)

        #: When
        occurrences = judged(MissingFrontmatter, subject)

        #: Then
        assert occurrences == (), 'a block that is there but not YAML is invalid-yaml, never missing-frontmatter'

    def test_check_with_a_mapping_reports_nothing(self) -> None:
        #: Given
        text = dedent("""\
            ---
            name: setup
            ---
            # Setup
            """)
        subject = FakeDocumentDatabase(text, corpus='guide', structure=STRUCTURE)

        #: When
        occurrences = judged(MissingFrontmatter, subject)

        #: Then
        assert occurrences == (), 'a block that decoded to a mapping is there'

    def test_message_names_the_missing_block(self) -> None:
        #: Given
        occurrence = MissingFrontmatter(owner=DOCUMENT_OWNER, line=LineNumber(NonZeroUnsignedInt(1)))

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'no `---` delimited frontmatter block', 'the message names the block that is missing'

    def test_labels_say_the_file_must_open_with_a_delimiter(self) -> None:
        #: Given
        occurrence = MissingFrontmatter(owner=DOCUMENT_OWNER, line=LineNumber(NonZeroUnsignedInt(1)))

        #: When
        labels = occurrence.labels()

        #: Then
        assert labels == (
            Label(Here(LineNumber(NonZeroUnsignedInt(1))), 'a `---` delimited block is expected here'),
        ), 'the label is on line 1, where the delimiter is missing'

    def test_children_with_a_document_point_at_its_specification_and_say_how_to_open_the_block(self) -> None:
        #: Given
        occurrence = MissingFrontmatter(owner=DOCUMENT_OWNER, line=LineNumber(NonZeroUnsignedInt(1)))

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note('the frontmatter schema is set here', at=Elsewhere(SPEC)),
            Help('open the file with a `---` line, the fields, and a closing `---` line'),
        ), "a document lists none of its fields: the required ones are not this rule's input"

    def test_children_with_a_skill_name_the_agent_skills_specification_and_show_the_skeleton(self) -> None:
        #: Given
        occurrence = MissingFrontmatter(owner=SKILL_OWNER, line=LineNumber(NonZeroUnsignedInt(1)))

        #: When
        children = occurrence.children()

        #: Then
        skeleton = dedent("""\
            for example:
            ---
            name: review
            description: …
            ---""")
        assert children == (
            Note("the Agent Skills specification governs a SKILL.md's frontmatter"),
            Help('open the file with a `---` line, the fields, and a closing `---` line'),
            Note(skeleton),
        ), 'the specification note has no location, since no file holds it, and the skeleton names the directory'
