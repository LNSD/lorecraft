"""`FM005`, `duplicate-key`, over a document's or a skill's frontmatter.

Every case is a document or a skill entrypoint (`SKILL.md`) written as text, read through a fake database that
parses its frontmatter as
the real parser does, which lists every key a mapping writes again, at any depth, with its line; no file is read from
disk.
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

from ..duplicate_key import DuplicateKey

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


def _duplicate(*, key: str) -> DuplicateKey:
    """A document's occurrence of `key` on line 4, first written on line 3, the last write.

    Args:
        key: The key written again.
    """
    return DuplicateKey(
        owner=DOCUMENT_OWNER,
        line=LineNumber(NonZeroUnsignedInt(4)),
        key=key,
        first_line=LineNumber(NonZeroUnsignedInt(3)),
        kept_line=LineNumber(NonZeroUnsignedInt(4)),
    )


@pytest.mark.unit
class TestDuplicateKey:
    def test_check_with_a_key_written_three_times_reports_each_later_occurrence_against_the_first(self) -> None:
        #: Given
        text = dedent("""\
            ---
            name: setup
            name: setup
            description: Install.
            name: other
            ---
            # Setup
            """)
        subject = FakeDocumentDatabase(text, corpus='guide', structure=STRUCTURE)

        #: When
        occurrences = judged(DuplicateKey, subject)

        #: Then
        first = LineNumber(NonZeroUnsignedInt(2))
        last = LineNumber(NonZeroUnsignedInt(5))
        assert occurrences == (
            DuplicateKey(
                owner=DOCUMENT_OWNER,
                line=LineNumber(NonZeroUnsignedInt(3)),
                key='name',
                first_line=first,
                kept_line=last,
            ),
            DuplicateKey(owner=DOCUMENT_OWNER, line=last, key='name', first_line=first, kept_line=last),
        ), (
            'each later occurrence is reported on its own line, pointing back at the first, not at the one before, '
            'and at the last, whose value is the one read'
        )

    def test_check_with_a_nested_key_of_a_top_level_name_reports_nothing(self) -> None:
        #: Given
        text = dedent("""\
            ---
            name: setup
            metadata:
              name: inner
            ---
            # Setup
            """)
        subject = FakeDocumentDatabase(text, corpus='guide', structure=STRUCTURE)

        #: When
        occurrences = judged(DuplicateKey, subject)

        #: Then
        assert occurrences == (), 'a key nested in a value is written once in its own mapping, so it repeats none'

    def test_check_with_a_key_repeated_in_a_nested_mapping_reports_the_later_line(self) -> None:
        #: Given
        text = dedent("""\
            ---
            name: setup
            metadata:
              author: a
              author: b
            ---
            """)
        subject = FakeDocumentDatabase(text, corpus='guide', structure=STRUCTURE)

        #: When
        occurrences = judged(DuplicateKey, subject)

        #: Then
        assert occurrences == (
            DuplicateKey(
                owner=DOCUMENT_OWNER,
                line=LineNumber(NonZeroUnsignedInt(5)),
                key='author',
                first_line=LineNumber(NonZeroUnsignedInt(4)),
                kept_line=LineNumber(NonZeroUnsignedInt(5)),
            ),
        ), 'a nested key written again is reported on its own line, pointing back at its first'

    def test_check_with_a_skill_repeating_a_key_reports_it_under_no_specification_file(self) -> None:
        #: Given
        text = dedent("""\
            ---
            name: review
            name: review
            ---
            """)
        subject = FakeSkillDatabase(text)

        #: When
        occurrences = judged(DuplicateKey, subject)

        #: Then
        assert occurrences == (
            DuplicateKey(
                owner=SKILL_OWNER,
                line=LineNumber(NonZeroUnsignedInt(3)),
                key='name',
                first_line=LineNumber(NonZeroUnsignedInt(2)),
                kept_line=LineNumber(NonZeroUnsignedInt(3)),
            ),
        ), 'the package states the rule for a skill'

    def test_check_with_no_key_repeated_reports_nothing(self) -> None:
        #: Given
        text = dedent("""\
            ---
            name: setup
            description: Install.
            ---
            # Setup
            """)
        subject = FakeDocumentDatabase(text, corpus='guide', structure=STRUCTURE)

        #: When
        occurrences = judged(DuplicateKey, subject)

        #: Then
        assert occurrences == (), 'a mapping that writes each key once repeats nothing'

    def test_check_with_no_block_reports_nothing(self) -> None:
        #: Given
        subject = FakeDocumentDatabase('# Setup\n', corpus='guide', structure=STRUCTURE)

        #: When
        occurrences = judged(DuplicateKey, subject)

        #: Then
        assert occurrences == (), 'a subject with no block has no key to repeat'

    def test_message_names_the_key(self) -> None:
        #: Given
        occurrence = _duplicate(key='description')

        #: When
        message = occurrence.message()

        #: Then
        assert message == "duplicate key 'description'", (
            'the message names the key as its repr; the labels name the lines'
        )

    def test_message_with_a_key_holding_a_newline_prints_it_on_one_line(self) -> None:
        #: Given
        occurrence = _duplicate(key='a\nb')

        #: When
        message = occurrence.message()

        #: Then
        assert message == "duplicate key 'a\\nb'", (
            'a newline in the key is printed as its escape, so the message stays on one line'
        )

    def test_message_with_a_lone_surrogate_key_prints_it_escaped(self) -> None:
        #: Given
        occurrence = _duplicate(key='\ud83d')

        #: When
        message = occurrence.message()

        #: Then
        assert message == "duplicate key '\\ud83d'", (
            'a key no terminal can print is named by its escape, so the message can be written out'
        )

    def test_labels_mark_it_and_point_at_the_first_occurrence(self) -> None:
        #: Given
        occurrence = _duplicate(key='description')

        #: When
        labels = occurrence.labels()

        #: Then
        assert labels == (
            Label(Here(LineNumber(NonZeroUnsignedInt(4))), 'written again here'),
            Label(Here(LineNumber(NonZeroUnsignedInt(3))), 'first written here'),
        ), 'a label marks the repeated line, and another the line the key was first written on'

    def test_labels_with_a_repeat_on_one_line_mark_it_once(self) -> None:
        #: Given
        text = dedent("""\
            ---
            name: setup
            size: {w: 1, w: 2}
            ---
            """)
        subject = FakeDocumentDatabase(text, corpus='guide', structure=STRUCTURE)
        (occurrence,) = judged(DuplicateKey, subject)

        #: When
        labels = occurrence.labels()

        #: Then
        assert labels == (Label(Here(LineNumber(NonZeroUnsignedInt(3))), 'written again here'),), (
            'one line, so one label'
        )

    def test_children_with_the_last_occurrence_do_not_point_at_the_value_kept(self) -> None:
        #: Given
        occurrence = _duplicate(key='description')

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note('the frontmatter schema is set here', at=Elsewhere(SPEC)),
            Help("write 'description' once, with the value meant"),
        ), 'a note points at the specification, a help names the key to write once; this line is the one kept'

    def test_children_before_the_last_point_at_the_value_kept(self) -> None:
        #: Given
        occurrence = DuplicateKey(
            owner=DOCUMENT_OWNER,
            line=LineNumber(NonZeroUnsignedInt(4)),
            key='description',
            first_line=LineNumber(NonZeroUnsignedInt(3)),
            kept_line=LineNumber(NonZeroUnsignedInt(6)),
        )

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note('the frontmatter schema is set here', at=Elsewhere(SPEC)),
            Help("write 'description' once, with the value meant"),
            Note('the value written last is the one read', at=Here(LineNumber(NonZeroUnsignedInt(6)))),
        ), 'a note on the last line says that value is the one read, since this one is not it'

    def test_children_with_a_skill_name_the_agent_skills_specification(self) -> None:
        #: Given
        occurrence = DuplicateKey(
            owner=SKILL_OWNER,
            line=LineNumber(NonZeroUnsignedInt(3)),
            key='name',
            first_line=LineNumber(NonZeroUnsignedInt(2)),
            kept_line=LineNumber(NonZeroUnsignedInt(3)),
        )

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note("the Agent Skills specification governs a SKILL.md's frontmatter"),
            Help("write 'name' once, with the value meant"),
        ), 'a note names the external specification, with no location, whatever the block holds'
