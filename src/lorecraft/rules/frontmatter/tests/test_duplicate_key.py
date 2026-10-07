"""`FM005`, `duplicate-key`, over a document's or a skill's frontmatter.

Every case is a document or a `SKILL.md` written as text, read through a fake context that parses its frontmatter as
the real parser does, which keeps every top-level key once per occurrence with its line; no file is read from disk.
"""

from typing import Final

import pytest

from lorecraft.core.path import RootRelativePath
from lorecraft.project.syntax import LineNumber
from lorecraft.rules.location import Elsewhere, Help, Here, Label, Note
from lorecraft.rules.tests.fake_context import FakeDocumentContext, FakeSkillContext, structure_spec_path

from ..duplicate_key import DuplicateKey

STRUCTURE: Final[str] = '{"frontmatter": {"type": "object"}}'
"""A corpus structure specification whose frontmatter schema accepts any mapping."""

SPEC: Final[RootRelativePath] = structure_spec_path('guide')
"""Where the corpus structure specification lies."""


def _duplicate(*, key: str) -> DuplicateKey:
    """A document's occurrence of `key` on line 4, first written on line 3, the last write.

    Args:
        key: The key written again.
    """
    return DuplicateKey(
        spec=SPEC,
        line=LineNumber.from_int(4),
        key=key,
        first_line=LineNumber.from_int(3),
        kept_line=LineNumber.from_int(4),
    )


@pytest.mark.unit
class TestDuplicateKey:
    def test_check_with_a_key_written_three_times_reports_each_later_occurrence_against_the_first(self) -> None:
        #: Given
        text = '---\nname: setup\nname: setup\ndescription: Install.\nname: other\n---\n# Setup\n'
        subject = FakeDocumentContext(text, corpus='guide', structure=STRUCTURE)

        #: When
        occurrences = DuplicateKey.check(subject)

        #: Then
        first = LineNumber.from_int(2)
        last = LineNumber.from_int(5)
        assert occurrences == (
            DuplicateKey(spec=SPEC, line=LineNumber.from_int(3), key='name', first_line=first, kept_line=last),
            DuplicateKey(spec=SPEC, line=last, key='name', first_line=first, kept_line=last),
        ), (
            'each later occurrence is reported on its own line, pointing back at the first, not at the one before, '
            'and at the last, whose value YAML keeps'
        )

    def test_check_with_a_nested_key_of_a_top_level_name_reports_nothing(self) -> None:
        #: Given
        text = '---\nname: setup\nmetadata:\n  name: inner\n---\n# Setup\n'
        subject = FakeDocumentContext(text, corpus='guide', structure=STRUCTURE)

        #: When
        occurrences = DuplicateKey.check(subject)

        #: Then
        assert occurrences == (), 'a key nested in a value is not a top-level key, so it repeats none'

    def test_check_with_a_skill_repeating_a_key_reports_it_under_no_specification_file(self) -> None:
        #: Given
        subject = FakeSkillContext('---\nname: review\nname: review\n---\n')

        #: When
        occurrences = DuplicateKey.check(subject)

        #: Then
        assert occurrences == (
            DuplicateKey(
                spec=None,
                line=LineNumber.from_int(3),
                key='name',
                first_line=LineNumber.from_int(2),
                kept_line=LineNumber.from_int(3),
            ),
        ), 'the package states the rule for a skill'

    def test_check_with_no_key_repeated_reports_nothing(self) -> None:
        #: Given
        text = '---\nname: setup\ndescription: Install.\n---\n# Setup\n'
        subject = FakeDocumentContext(text, corpus='guide', structure=STRUCTURE)

        #: When
        occurrences = DuplicateKey.check(subject)

        #: Then
        assert occurrences == (), 'a mapping that writes each key once repeats nothing'

    def test_check_with_no_block_reports_nothing(self) -> None:
        #: Given
        subject = FakeDocumentContext('# Setup\n', corpus='guide', structure=STRUCTURE)

        #: When
        occurrences = DuplicateKey.check(subject)

        #: Then
        assert occurrences == (), 'a subject with no block has no key to repeat'

    def test_message_with_an_occurrence_names_the_key(self) -> None:
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

    def test_labels_with_an_occurrence_mark_it_and_point_at_the_first_occurrence(self) -> None:
        #: Given
        occurrence = _duplicate(key='description')

        #: When
        labels = occurrence.labels()

        #: Then
        assert labels == (
            Label(Here(LineNumber.from_int(4)), 'written again here'),
            Label(Here(LineNumber.from_int(3)), 'first written here'),
        ), 'a label marks the repeated line, and another the line the key was first written on'

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

    def test_children_with_an_occurrence_before_the_last_point_at_the_value_kept(self) -> None:
        #: Given
        occurrence = DuplicateKey(
            spec=SPEC,
            line=LineNumber.from_int(4),
            key='description',
            first_line=LineNumber.from_int(3),
            kept_line=LineNumber.from_int(6),
        )

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note('the frontmatter schema is set here', at=Elsewhere(SPEC)),
            Help("write 'description' once, with the value meant"),
            Note('the value written last is the one YAML keeps', at=Here(LineNumber.from_int(6))),
        ), 'a note on the last line says YAML keeps that value, since this one is not it'

    def test_children_with_a_skill_name_the_agent_skills_specification(self) -> None:
        #: Given
        occurrence = DuplicateKey(
            spec=None,
            line=LineNumber.from_int(3),
            key='name',
            first_line=LineNumber.from_int(2),
            kept_line=LineNumber.from_int(3),
        )

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note("the Agent Skills specification governs a SKILL.md's frontmatter"),
            Help("write 'name' once, with the value meant"),
        ), 'a note names the external specification, with no location, whatever the block holds'
