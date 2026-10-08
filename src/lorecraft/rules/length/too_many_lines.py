"""`LEN002`: a skill's `SKILL.md` is longer than the Agent Skills specification's line budget."""

from dataclasses import dataclass
from typing import ClassVar, Final, Self

from lorecraft.project.context import SkillContext
from lorecraft.project.syntax import LineNumber
from lorecraft.rules.declaration import Level, Release, RuleCode, RuleName, rule
from lorecraft.rules.location import Help, Here, Label, Note, Subdiagnostic
from lorecraft.rules.subject import SkillRule

from .__ruleset__ import GROUP_ID

_LINE_BUDGET: Final[int] = 500
"""The most lines a `SKILL.md` may hold, frontmatter included.

The specification says "Keep your main `SKILL.md` under 500 lines"
(https://agentskills.io/specification#progressive-disclosure); a file of exactly 500 lines is within it, and
its line 501 is the first past the budget.
"""

_FIRST_LINE_PAST_BUDGET: Final[LineNumber] = LineNumber.from_int(_LINE_BUDGET + 1)
"""Where an occurrence is reported: the first line the budget does not allow."""


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class TooManyLines(SkillRule):
    """A skill's `SKILL.md` is longer than the Agent Skills specification allows.

    ## What it does

    Checks for skills whose `SKILL.md` holds more than 500 lines, the budget the Agent Skills specification sets.
    The whole file counts: frontmatter, blank lines and code blocks as much as prose. A file of exactly 500 lines
    is within the budget. No specification in the repository sets or changes it.

    ## Why is this bad?

    An agent loads the whole `SKILL.md` every time the skill activates, so every line of it is spent on every
    activation, whether that activation needs it or not.

    ## Example

    `.agents/skills/review/SKILL.md`, at 612 lines:

    ```markdown
    ---
    name: review
    description: Review a change before it is merged.
    ---

    # Review

    Read the diff, then walk the checklist below.

    ## Checklist

    <!-- ... 601 more lines, one subsection per kind of change -->
    ```

    ## Use instead

    Move what most activations do not need into a file under `references/`, and say when to read it:

    ```markdown
    ---
    name: review
    description: Review a change before it is merged.
    ---

    # Review

    Read the diff, then walk the checklist below.

    ## Checklist

    Read [the checklist](references/checklist.md) for the kind of change under review.
    ```

    Attributes:
        spec: Always `None`: the package states the rule, after the Agent Skills specification.
        line_count: The lines in the skill's whole `SKILL.md`; always past the budget, so line 501 exists.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 2)
    NAME: ClassVar[RuleName] = RuleName('too-many-lines')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')

    spec: None = None
    line_count: int

    def message(self) -> str:
        """Name the lines found against the budget they exceed."""
        return f'too many lines ({self.line_count} > {_LINE_BUDGET})'

    def labels(self) -> tuple[Label, ...]:
        """Mark where the budget ends, and how many lines the file runs past it."""
        return (
            Label(
                Here(self.line),
                f'the budget ends before this line; lines past it: {self.line_count - _LINE_BUDGET}',
            ),
        )

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Say where the budget comes from, and where to move the lines over it."""
        return (
            Note(f'the Agent Skills specification keeps a SKILL.md to at most {_LINE_BUDGET} lines'),
            Help(
                'move what most activations do not need into files under references/, and say in SKILL.md when to '
                'read each'
            ),
        )

    @classmethod
    def check(cls, subject: SkillContext) -> tuple[Self, ...]:
        """The one occurrence, on the first line past the budget, when the `SKILL.md` runs over it; none otherwise.

        Args:
            subject: The skill, whose whole `SKILL.md` is counted.
        """
        line_count = subject.lines().value
        if line_count <= _LINE_BUDGET:
            return ()
        return (cls(line=_FIRST_LINE_PAST_BUDGET, line_count=line_count),)
