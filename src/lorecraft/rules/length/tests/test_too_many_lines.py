"""`LEN002`, `too-many-lines`, over a skill's whole-`SKILL.md` line count.

Every case is a `SKILL.md` written as text, read through a fake database that counts its lines as the real counter
does; no skill is read from disk.
"""

from typing import Final

import pytest

from lib.overruns import overrun
from lorecraft.core.num import NonZeroUnsignedInt
from lorecraft.project.syntax import LineNumber
from lorecraft.rules.location import Help, Here, Label, Note
from lorecraft.rules.tests.fake_database import (
    FakeDocumentDatabase,
    FakeSkillDatabase,
    judged,
    structure_spec_path,
)

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
    def test_check_with_a_skill_over_the_budget_reports_it_on_the_first_line_past_it(self) -> None:
        #: Given
        subject = FakeSkillDatabase(_skill_of(501))

        #: When
        occurrences = judged(TooManyLines, subject)

        #: Then
        assert occurrences == (TooManyLines(line=LineNumber(NonZeroUnsignedInt(501)), overrun=overrun(501, 500)),), (
            'a SKILL.md one line over the budget is one occurrence, on line 501, the first line past it'
        )

    def test_check_with_a_skill_at_the_budget_reports_nothing(self) -> None:
        #: Given
        subject = FakeSkillDatabase(_skill_of(500))

        #: When
        occurrences = judged(TooManyLines, subject)

        #: Then
        assert occurrences == (), 'the budget is the most lines allowed, so a SKILL.md of exactly 500 lines fits it'

    def test_check_with_a_document_over_its_structure_line_budget_reports_the_budget(self) -> None:
        #: Given
        subject = FakeDocumentDatabase('# Guide\n' + 'line\n' * 899, corpus='code', structure='{"lines": 50}')

        #: When
        occurrences = judged(TooManyLines, subject)

        #: Then
        assert occurrences == (
            TooManyLines(
                spec=structure_spec_path('code'),
                line=LineNumber(NonZeroUnsignedInt(51)),
                overrun=overrun(900, 50),
            ),
        ), 'a document over its structure line budget reports the limit and its source'

    def test_message_names_the_lines_and_the_budget(self) -> None:
        #: Given
        occurrence = TooManyLines(line=LineNumber(NonZeroUnsignedInt(501)), overrun=overrun(612, 500))

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'too many lines (612 > 500)', 'the message sets the line count against the budget'

    def test_message_with_an_overrun_of_another_cap_names_that_cap(self) -> None:
        #: Given
        occurrence = TooManyLines(line=LineNumber(NonZeroUnsignedInt(501)), overrun=overrun(700, 600))

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'too many lines (700 > 600)', 'the message reads the cap from the overrun it holds'

    def test_labels_mark_where_the_budget_ends_and_the_lines_past_it(self) -> None:
        #: Given
        occurrence = TooManyLines(line=LineNumber(NonZeroUnsignedInt(501)), overrun=overrun(612, 500))

        #: When
        labels = occurrence.labels()

        #: Then
        assert labels == (
            Label(Here(LineNumber(NonZeroUnsignedInt(501))), 'the budget ends before this line; lines past it: 112'),
        ), 'the label sits on line 501 and gives the lines past the budget'

    def test_children_name_the_budget_and_say_where_to_move_the_lines(self) -> None:
        #: Given
        occurrence = TooManyLines(line=LineNumber(NonZeroUnsignedInt(501)), overrun=overrun(612, 500))

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note('the Agent Skills specification keeps a SKILL.md to at most 500 lines'),
            Help(
                'move what most activations do not need into files under references/, and say in SKILL.md when to '
                'read each'
            ),
        ), 'a note names where the budget comes from, and a help where to move the lines over it'
