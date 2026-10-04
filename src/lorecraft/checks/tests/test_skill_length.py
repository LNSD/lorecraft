"""The line budget over the number of lines in a skill's `SKILL.md`.

`validate_skill_length` is pure, so every case here is a line count; no file is read and no line is counted.
"""

from typing import Final

import pytest

from lorecraft.project.syntax import LineNumber

from ..reporting import Note, NoteKind, Violation
from ..skill_length import validate_skill_length

_LINES_BUDGET_HELP: Final[tuple[Note, ...]] = (
    Note(
        NoteKind.HELP,
        'move detail most activations do not need into files under references/, and say in SKILL.md when to read each',
    ),
)
"""The help a `skill.lines-budget` violation carries, whatever the count."""


@pytest.mark.unit
class TestValidateSkillLength:
    def test_validate_skill_length_with_501_lines_reports_it_on_line_1_with_help(self) -> None:
        #: Given
        line_count = 501

        #: When
        result = validate_skill_length(line_count=line_count)

        #: Then
        assert result.violations == (
            Violation(
                line=LineNumber.from_int(1),
                rule='skill.lines-budget',
                message='501 lines; the budget is 500',
                notes=_LINES_BUDGET_HELP,
            ),
        ), 'one line over the budget is one violation on line 1, the count and the budget in the message'

    def test_validate_skill_length_with_500_lines_returns_no_violations(self) -> None:
        #: Given
        line_count = 500

        #: When
        result = validate_skill_length(line_count=line_count)

        #: Then
        assert result.violations == (), 'the budget is the most lines allowed, so a file of 500 lines conforms'

    def test_validate_skill_length_with_499_lines_returns_no_violations(self) -> None:
        #: Given
        line_count = 499

        #: When
        result = validate_skill_length(line_count=line_count)

        #: Then
        assert result.violations == (), 'a file under the budget conforms'

    def test_validate_skill_length_with_far_more_lines_reports_the_count_it_was_given(self) -> None:
        #: Given
        line_count = 1200

        #: When
        result = validate_skill_length(line_count=line_count)

        #: Then
        assert result.violations == (
            Violation(
                line=LineNumber.from_int(1),
                rule='skill.lines-budget',
                message='1200 lines; the budget is 500',
                notes=_LINES_BUDGET_HELP,
            ),
        ), 'however far over the budget, the file is one violation, and the message carries its count'
