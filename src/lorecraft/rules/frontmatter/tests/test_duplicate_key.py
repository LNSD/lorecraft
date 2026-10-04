"""`FM005`, `duplicate-key`, over a document's or a skill's frontmatter block.

The rule is pure, so every case here is a frontmatter block written as a literal; no file is read. Which keys repeat,
and where, is located by the input's builder, and tested with it.
"""

from typing import Final

import pytest

from lorecraft.core.path import RootRelativePath
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.syntax import LineNumber, MissingFrontmatter
from lorecraft.rules.inputs import (
    DocumentFrontmatterOwner,
    FrontmatterBlockInput,
    FrontmatterFields,
    RepeatedKey,
    SkillFrontmatterOwner,
)
from lorecraft.rules.location import Elsewhere, Help, Here, Label, Note

from ..duplicate_key import DuplicateKey

SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/guide.structure.json')
"""The structure specification whose frontmatter schema governs the document."""

DOCUMENT: Final[DocumentFrontmatterOwner] = DocumentFrontmatterOwner(filename=AspectFilename.parse('setup'), spec=SPEC)
"""A document `setup` the schema in `SPEC` governs."""

SKILL: Final[SkillFrontmatterOwner] = SkillFrontmatterOwner(directory_name='review', link_target=None)
"""A skill listed as `review`, not through a link."""


def _repeating(*repeated: RepeatedKey) -> FrontmatterFields:
    """A mapping with no `name` that writes these keys again.

    Args:
        repeated: Each occurrence of a key after its first, in document order.
    """
    return FrontmatterFields(name=None, repeated_keys=repeated)


def _repeated(key: str, line: int, first_line: int) -> RepeatedKey:
    """One occurrence of a key after its first.

    Args:
        key: The key written again.
        line: The line this occurrence is written on.
        first_line: The line the key's first occurrence is written on.
    """
    return RepeatedKey(key=key, line=LineNumber.from_int(line), first_line=LineNumber.from_int(first_line))


@pytest.mark.unit
class TestDuplicateKey:
    def test_check_with_a_key_written_three_times_reports_each_later_occurrence_against_the_first(self) -> None:
        #: Given
        frontmatter = _repeating(_repeated('name', 3, 2), _repeated('name', 5, 2))
        subject = FrontmatterBlockInput(frontmatter=frontmatter, owner=DOCUMENT)

        #: When
        occurrences = DuplicateKey.check(subject)

        #: Then
        first = LineNumber.from_int(2)
        assert occurrences == (
            DuplicateKey(spec=SPEC, line=LineNumber.from_int(3), key='name', first_line=first),
            DuplicateKey(spec=SPEC, line=LineNumber.from_int(5), key='name', first_line=first),
        ), 'each later occurrence is reported on its own line, pointing back at the first'

    def test_check_with_a_skill_repeating_a_key_reports_it_under_no_specification_file(self) -> None:
        #: Given
        subject = FrontmatterBlockInput(frontmatter=_repeating(_repeated('name', 3, 2)), owner=SKILL)

        #: When
        occurrences = DuplicateKey.check(subject)

        #: Then
        assert occurrences == (
            DuplicateKey(spec=None, line=LineNumber.from_int(3), key='name', first_line=LineNumber.from_int(2)),
        ), 'the package states the rule for a skill'

    def test_check_with_no_key_repeated_reports_nothing(self) -> None:
        #: Given
        subject = FrontmatterBlockInput(frontmatter=_repeating(), owner=DOCUMENT)

        #: When
        occurrences = DuplicateKey.check(subject)

        #: Then
        assert occurrences == (), 'a mapping that writes each key once repeats nothing'

    def test_check_with_no_block_reports_nothing(self) -> None:
        #: Given
        subject = FrontmatterBlockInput(frontmatter=MissingFrontmatter(), owner=DOCUMENT)

        #: When
        occurrences = DuplicateKey.check(subject)

        #: Then
        assert occurrences == (), 'a subject with no block has no key to repeat'

    def test_message_with_an_occurrence_names_the_key_and_its_first_line(self) -> None:
        #: Given
        occurrence = DuplicateKey(
            spec=SPEC, line=LineNumber.from_int(4), key='description', first_line=LineNumber.from_int(3)
        )

        #: When
        message = occurrence.message()

        #: Then
        assert message == "duplicate key 'description', already written on line 3", (
            'the message names the key as its repr, and the line of its first occurrence'
        )

    def test_labels_with_an_occurrence_point_at_the_first_occurrence(self) -> None:
        #: Given
        occurrence = DuplicateKey(
            spec=SPEC, line=LineNumber.from_int(4), key='description', first_line=LineNumber.from_int(3)
        )

        #: When
        labels = occurrence.labels()

        #: Then
        assert labels == (Label(Here(LineNumber.from_int(3)), 'first written here'),), (
            'a label points at the line the key was first written on'
        )

    def test_children_with_a_document_point_at_its_specification_and_name_the_key(self) -> None:
        #: Given
        occurrence = DuplicateKey(
            spec=SPEC, line=LineNumber.from_int(4), key='description', first_line=LineNumber.from_int(3)
        )

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note('the frontmatter schema is set here', at=Elsewhere(SPEC)),
            Help("write 'description' once, with the value meant"),
        ), 'a note points at the specification, a help names the key to write once'

    def test_children_with_a_skill_name_the_agent_skills_specification(self) -> None:
        #: Given
        occurrence = DuplicateKey(spec=None, line=LineNumber.from_int(3), key='name', first_line=LineNumber.from_int(2))

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note("the Agent Skills specification governs a SKILL.md's frontmatter"),
            Help("write 'name' once, with the value meant"),
        ), 'a note names the external specification, with no location, whatever the block holds'
