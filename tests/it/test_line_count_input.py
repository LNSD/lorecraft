"""The line-count input, built from a database's `skill_lines` query for one decoded skill.

The package governs the line count, so the input is built for every skill whose `SKILL.md` decodes; it is tested
over a database opened on an in-memory snapshot.
"""

from typing import Final

import pytest

from lorecraft.checks.inputs import build_line_count_input
from lorecraft.core.num import UnsignedInt
from lorecraft.core.path import RootRelativePath
from lorecraft.project.database import Database, SkillText
from lorecraft.project.skill import SkillRef
from lorecraft.rules.inputs import LineCountInput
from lorecraft.vfs import Snapshot

REVIEW: Final[SkillRef] = SkillRef(RootRelativePath.parse('.agents/skills/review'))
"""A skill an agent reaches under `.agents/skills`."""


def _snapshot(skill: bytes) -> Snapshot:
    """A snapshot holding the one skill `REVIEW`, and no specification.

    Args:
        skill: Bytes of the skill's `SKILL.md`.
    """
    return Snapshot.from_tree({'.agents': {'skills': {'review': {'SKILL.md': skill}}}})


def _skill_text(database: Database, ref: SkillRef) -> SkillText:
    """The witness of a skill whose `SKILL.md` the test wrote as UTF-8, as the database decodes it.

    Args:
        database: The database the `SKILL.md` is decoded by.
        ref: A skill whose `SKILL.md` bytes are UTF-8.
    """
    source = database.skill_text(ref)
    assert isinstance(source, SkillText), f'{ref.path} was written as UTF-8, so it decodes'
    return source


@pytest.mark.it
class TestBuildLineCountInput:
    def test_build_line_count_input_with_a_skill_holds_the_lines_of_its_whole_skill_file(self) -> None:
        #: Given
        # three lines of frontmatter and three of body, in a repository with no specification at all
        database = Database(_snapshot(b'---\nname: review\n---\n# Review\n\nRead the diff.\n'))
        source = _skill_text(database, REVIEW)

        #: When
        subject = build_line_count_input(database, source)

        #: Then
        assert subject == LineCountInput(line_count=UnsignedInt(6)), (
            'the frontmatter counts too, and the package governs the count, so no specification is needed'
        )
