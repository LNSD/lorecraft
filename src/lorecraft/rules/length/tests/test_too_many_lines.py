"""`LEN002`, `too-many-lines`, over a skill's whole-`SKILL.md` line count.

The rule is pure, so every case here is a line count; no skill is read.
"""

import pytest

from lorecraft.core.num import UnsignedInt
from lorecraft.project.syntax import LineNumber
from lorecraft.rules.inputs import LineCountInput
from lorecraft.rules.location import Help, Note

from ..too_many_lines import TooManyLines


@pytest.mark.unit
class TestTooManyLines:
    def test_check_with_a_skill_over_the_budget_reports_it_on_line_1(self) -> None:
        #: Given
        subject = LineCountInput(line_count=UnsignedInt(501))

        #: When
        occurrences = TooManyLines.check(subject)

        #: Then
        assert occurrences == (TooManyLines(line=LineNumber.from_int(1), line_count=501),), (
            'a SKILL.md one line over the budget is one occurrence, on line 1'
        )

    def test_check_with_a_skill_at_the_budget_reports_nothing(self) -> None:
        #: Given
        subject = LineCountInput(line_count=UnsignedInt(500))

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
