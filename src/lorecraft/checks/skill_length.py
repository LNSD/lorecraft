"""Hold one skill's `SKILL.md` to the line budget the Agent Skills specification sets.

An agent loads the whole `SKILL.md` each time the skill activates, and every other file of the skill only when the
`SKILL.md` sends it there, so the specification asks to keep the `SKILL.md` short and to move detail into those
other files. The budget counts every line of the file, frontmatter included, since the agent loads all of them.

The check is pure: it takes the number of lines in the `SKILL.md` and returns violations. Reading the file and
counting its lines happen above it, in `checks.run` and the database. It is the sibling of the frontmatter half in
`skill`, and reports in the same `SkillCheckResult`.
"""

from typing import Final

from lorecraft.project.syntax import LineNumber

from .reporting import Note, NoteKind, Violation
from .skill import SkillCheckResult

_LINE_BUDGET: Final[int] = 500
"""The most lines a `SKILL.md` may hold, frontmatter included.

The specification says "Keep your main `SKILL.md` under 500 lines"
(https://agentskills.io/specification#progressive-disclosure); a file of exactly 500 lines is within it.
"""

_FIRST_LINE: Final[LineNumber] = LineNumber.from_int(1)
"""Where a budget violation is reported: it concerns the whole file, not one line of it."""


def validate_skill_length(*, line_count: int) -> SkillCheckResult:
    """Check the number of lines in one skill's `SKILL.md` against the budget. Pure: raises nothing.

    A `SKILL.md` of more lines than the budget is `skill.lines-budget`, on line 1, with a help note on how to fix
    it; one within the budget conforms.

    Args:
        line_count: The lines in the skill's whole `SKILL.md`, frontmatter included, as `count_lines` counts them.
    """
    if line_count <= _LINE_BUDGET:
        return SkillCheckResult(violations=())
    violation = Violation(
        line=_FIRST_LINE,
        rule='skill.lines-budget',
        message=f'{line_count} lines; the budget is {_LINE_BUDGET}',
        notes=(
            Note(
                NoteKind.HELP,
                'move detail most activations do not need into files under references/, and say in SKILL.md when '
                'to read each',
            ),
        ),
    )
    return SkillCheckResult(violations=(violation,))
