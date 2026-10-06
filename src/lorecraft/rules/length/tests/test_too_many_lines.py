"""`LEN002`, `too-many-lines`, over a skill's whole-`SKILL.md` line count.

Every case is a `SKILL.md` written as text, read through a fake context that counts its lines as the real counter
does; no skill is read from disk.
"""

from typing import Final

import pytest

from lorecraft.project.syntax import LineNumber
from lorecraft.rules.location import Help, Note
from lorecraft.rules.tests.fake_context import FakeSkillContext

from ..too_many_lines import TooManyLines

FRONTMATTER: Final[str] = '---\nname: review\ndescription: Review a change before it is merged.\n---\n'
"""A frontmatter of four lines."""


def _skill_of(lines: int) -> str:
    """A `SKILL.md` of exactly `lines` lines: `FRONTMATTER`, then one step per line.

    Args:
        lines: The lines the file holds; at least 4, for the frontmatter.
    """
    return FRONTMATTER + 'Run the next step.\n' * (lines - 4)


@pytest.mark.unit
class TestTooManyLines:
    def test_check_with_a_skill_over_the_budget_reports_it_on_line_1(self) -> None:
        #: Given
        subject = FakeSkillContext(_skill_of(501))

        #: When
        occurrences = TooManyLines.check(subject)

        #: Then
        assert occurrences == (TooManyLines(line=LineNumber.from_int(1), line_count=501),), (
            'a SKILL.md one line over the budget is one occurrence, on line 1'
        )

    def test_check_with_a_skill_at_the_budget_reports_nothing(self) -> None:
        #: Given
        subject = FakeSkillContext(_skill_of(500))

        #: When
        occurrences = TooManyLines.check(subject)

        #: Then
        assert occurrences == (), 'the budget is the most lines allowed, so a SKILL.md of exactly 500 lines fits it'

    def test_message_with_an_occurrence_names_the_lines_and_the_budget(self) -> None:
        #: Given
        occurrence = TooManyLines(line=LineNumber.from_int(1), line_count=612)

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'too many lines (612 > 500)', 'the message sets the line count against the budget'

    def test_children_with_an_occurrence_name_the_budget_and_say_where_to_move_the_lines(self) -> None:
        #: Given
        occurrence = TooManyLines(line=LineNumber.from_int(1), line_count=612)

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note('the Agent Skills specification keeps a SKILL.md under 500 lines'),
            Help(
                'move what most activations do not need into files under references/, and say in SKILL.md when to '
                'read each'
            ),
        ), 'a note names where the budget comes from, and a help where to move the lines over it'
