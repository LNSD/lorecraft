"""`FM004`, `name-mismatch`, over a document's or a skill's frontmatter.

Every case is a document or a skill entrypoint (`SKILL.md`) written as text, read through a fake database that
parses its frontmatter as
the real parser does; no file is read from disk. The name a document is held to is the fake's filename, `setup`, and
the name a skill is held to the directory the fake lists it under, `review`.
"""

from textwrap import dedent
from typing import Final

import pytest

from lorecraft.core.num import NonZeroUnsignedInt
from lorecraft.core.path import ROOT, PathComponent, RootRelativePath
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.schemas import DocumentFrontmatterOwner, SkillFrontmatterOwner
from lorecraft.project.syntax import LineNumber
from lorecraft.rules.location import Help, Here, Label, Note
from lorecraft.rules.tests.fake_database import FakeDocumentDatabase, FakeSkillDatabase, judged, structure_spec_path
from lorecraft.vfs import ResolvedPath

from ..name_mismatch import NameMismatch

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

SHIPPED: Final[ResolvedPath] = ResolvedPath(RootRelativePath.parse('skills/code-review'))
"""The directory a linked skill directory leads to, named otherwise than the listed one."""


@pytest.mark.unit
class TestNameMismatch:
    def test_check_with_a_document_named_otherwise_reports_it_on_the_name_line(self) -> None:
        #: Given
        text = dedent("""\
            ---
            description: Install the toolkit.
            name: installation
            ---
            # Setup
            """)
        subject = FakeDocumentDatabase(text, corpus='guide', structure=STRUCTURE)

        #: When
        occurrences = judged(NameMismatch, subject)

        #: Then
        assert occurrences == (
            NameMismatch(owner=DOCUMENT_OWNER, line=LineNumber(NonZeroUnsignedInt(3)), name='installation'),
        ), 'a name other than the filename is one occurrence, on the line the `name` key is written on'

    def test_check_with_a_name_written_twice_reports_the_last_value_on_its_line(self) -> None:
        #: Given
        text = dedent("""\
            ---
            name: setup
            metadata:
              name: inner
            name: installation
            ---
            # Setup
            """)
        subject = FakeDocumentDatabase(text, corpus='guide', structure=STRUCTURE)

        #: When
        occurrences = judged(NameMismatch, subject)

        #: Then
        assert occurrences == (
            NameMismatch(owner=DOCUMENT_OWNER, line=LineNumber(NonZeroUnsignedInt(5)), name='installation'),
        ), 'the last value of a repeated key is the one read, so it is compared, on its line; a nested key is not it'

    def test_check_with_a_document_named_for_its_filename_reports_nothing(self) -> None:
        #: Given
        text = dedent("""\
            ---
            name: setup
            ---
            # Setup
            """)
        subject = FakeDocumentDatabase(text, corpus='guide', structure=STRUCTURE)

        #: When
        occurrences = judged(NameMismatch, subject)

        #: Then
        assert occurrences == (), 'a name equal to the filename holds to the rule'

    def test_check_with_a_document_without_a_name_reports_nothing(self) -> None:
        #: Given
        text = dedent("""\
            ---
            title: Setup
            ---
            # Setup
            """)
        subject = FakeDocumentDatabase(text, corpus='guide', structure=STRUCTURE)

        #: When
        occurrences = judged(NameMismatch, subject)

        #: Then
        assert occurrences == (), "a missing `name` is the schema's to report, never this rule's"

    def test_check_with_a_name_that_is_not_a_string_reports_nothing(self) -> None:
        #: Given
        text = dedent("""\
            ---
            name: 42
            ---
            """)
        subject = FakeSkillDatabase(text)

        #: When
        occurrences = judged(NameMismatch, subject)

        #: Then
        assert occurrences == (), "a `name` of another type is the schema's to report, never this rule's"

    def test_check_with_a_block_that_is_not_a_mapping_reports_nothing(self) -> None:
        #: Given
        text = dedent("""\
            ---
            - installation
            ---
            # Setup
            """)
        subject = FakeDocumentDatabase(text, corpus='guide', structure=STRUCTURE)

        #: When
        occurrences = judged(NameMismatch, subject)

        #: Then
        assert occurrences == (), 'a block that is not a mapping has no `name` to compare'

    def test_check_with_a_skill_named_for_its_directory_reports_nothing(self) -> None:
        #: Given
        text = dedent("""\
            ---
            name: review
            ---
            """)
        subject = FakeSkillDatabase(text)

        #: When
        occurrences = judged(NameMismatch, subject)

        #: Then
        assert occurrences == (), 'a name equal to the listed directory name holds to the rule'

    def test_check_with_a_skill_named_otherwise_reports_it_with_its_link_target(self) -> None:
        #: Given
        text = dedent("""\
            ---
            name: code-review
            ---
            """)
        subject = FakeSkillDatabase(text, link_target=SHIPPED)

        #: When
        occurrences = judged(NameMismatch, subject)

        #: Then
        assert occurrences == (
            NameMismatch(
                owner=SkillFrontmatterOwner(directory_name=PathComponent.parse('review'), link_target=SHIPPED),
                line=LineNumber(NonZeroUnsignedInt(2)),
                name='code-review',
            ),
        ), 'a skill is held to the name it is listed under, never to the name of the directory a link leads to'

    def test_message_names_the_name_against_the_expected_one(self) -> None:
        #: Given
        occurrence = NameMismatch(owner=DOCUMENT_OWNER, line=LineNumber(NonZeroUnsignedInt(2)), name='installation')

        #: When
        message = occurrence.message()

        #: Then
        assert message == "`name` is 'installation', which is not the name it is found under", (
            'the message names the name written; the label names the one expected'
        )

    def test_labels_with_a_document_name_the_filename_expected_on_the_name_line(self) -> None:
        #: Given
        occurrence = NameMismatch(owner=DOCUMENT_OWNER, line=LineNumber(NonZeroUnsignedInt(2)), name='installation')

        #: When
        labels = occurrence.labels()

        #: Then
        assert labels == (Label(Here(LineNumber(NonZeroUnsignedInt(2))), 'expected `setup`'),), (
            'the label sits on the `name` line and names the filename'
        )

    def test_labels_with_a_skill_name_the_directory_name_expected_on_the_name_line(self) -> None:
        #: Given
        occurrence = NameMismatch(owner=SKILL_OWNER, line=LineNumber(NonZeroUnsignedInt(2)), name='code-review')

        #: When
        labels = occurrence.labels()

        #: Then
        assert labels == (Label(Here(LineNumber(NonZeroUnsignedInt(2))), 'expected `review`'),), (
            'the label sits on the `name` line and names the directory'
        )

    def test_children_with_a_document_name_the_filename_and_offer_the_rename(self) -> None:
        #: Given
        occurrence = NameMismatch(owner=DOCUMENT_OWNER, line=LineNumber(NonZeroUnsignedInt(2)), name='installation')

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note("a document's `name` must be its filename"),
            Help("set `name` to 'setup'"),
            Help("or rename the file to 'installation.md'"),
        ), 'a note says which name is expected, with no pointer to a schema, since none states it; two helps fix it'

    def test_children_with_a_skill_reached_through_a_link_name_where_it_leads(self) -> None:
        #: Given
        owner = SkillFrontmatterOwner(directory_name=PathComponent.parse('review'), link_target=SHIPPED)
        occurrence = NameMismatch(owner=owner, line=LineNumber(NonZeroUnsignedInt(2)), name='code-review')

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note("a skill's `name` must match its directory name"),
            Help("set `name` to 'review'"),
            Help("or rename the skill directory to 'code-review'"),
            Note("'review' is a link to 'skills/code-review'"),
        ), 'a skill whose listed directory links to one named otherwise carries a note naming where it leads, last'

    def test_children_with_a_skill_linked_to_a_directory_of_the_same_name_carry_no_link_note(self) -> None:
        #: Given
        same_name = ResolvedPath(RootRelativePath.parse('skills/review'))
        owner = SkillFrontmatterOwner(directory_name=PathComponent.parse('review'), link_target=same_name)
        occurrence = NameMismatch(owner=owner, line=LineNumber(NonZeroUnsignedInt(2)), name='code-review')

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note("a skill's `name` must match its directory name"),
            Help("set `name` to 'review'"),
            Help("or rename the skill directory to 'code-review'"),
        ), 'a link to a directory of the listed name explains nothing, so no note names it'

    def test_children_with_a_skill_name_over_the_length_cap_offer_no_directory_rename(self) -> None:
        #: Given
        occurrence = NameMismatch(owner=SKILL_OWNER, line=LineNumber(NonZeroUnsignedInt(2)), name='a' * 70)

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note("a skill's `name` must match its directory name"),
            Help("set `name` to 'review'"),
        ), 'a directory renamed to a name FM009 rejects would trade this finding for that one, so it is not offered'

    def test_children_with_a_skill_linked_to_the_root_name_the_repository_root(self) -> None:
        #: Given
        owner = SkillFrontmatterOwner(directory_name=PathComponent.parse('review'), link_target=ResolvedPath(ROOT))
        occurrence = NameMismatch(owner=owner, line=LineNumber(NonZeroUnsignedInt(2)), name='code-review')

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note("a skill's `name` must match its directory name"),
            Help("set `name` to 'review'"),
            Help("or rename the skill directory to 'code-review'"),
            Note("'review' is a link to the repository root"),
        ), 'the root, whose own name is empty, is named as such'
