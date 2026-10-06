"""A sample rule at `deny` over a skill's line count, which fires on every skill."""

from dataclasses import dataclass
from typing import ClassVar, Self

from lorecraft.project.context import SkillContext
from lorecraft.project.syntax import LineNumber
from lorecraft.rules.declaration import Level, Release, RuleCode, RuleName, rule
from lorecraft.rules.subject import SkillRule

from ..groups import SAMPLE


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class AnyLines(SkillRule):
    """A sample rule that fires once on every skill, whatever its line count.

    Attributes:
        line_count: The lines in the skill's whole `SKILL.md`.
    """

    CODE: ClassVar[RuleCode] = RuleCode(SAMPLE, 1)
    NAME: ClassVar[RuleName] = RuleName('any-lines')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('1.0.0')

    line_count: int

    def message(self) -> str:
        """Name the condition and the count."""
        return f'skill counted ({self.line_count} lines)'

    @classmethod
    def check(cls, subject: SkillContext) -> tuple[Self, ...]:
        """One occurrence at line 1, whatever the count.

        Args:
            subject: The skill judged.
        """
        return (cls(spec=None, line=LineNumber.from_int(1), line_count=subject.lines().value),)
