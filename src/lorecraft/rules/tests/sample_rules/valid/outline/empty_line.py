"""A sample rule in a subpackage: a line is empty."""

from dataclasses import dataclass
from typing import ClassVar, Self

from lorecraft.project.syntax import LineNumber
from lorecraft.rules.declaration import Level, Release, RuleCode, RuleName, rule
from lorecraft.rules.tests.sample_input import SampleLines, SampleLinesRule
from lorecraft.rules.tests.sample_rules.groups import SAMPLE


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class EmptyLine(SampleLinesRule):
    """A line is empty."""

    CODE: ClassVar[RuleCode] = RuleCode(SAMPLE, 1)
    NAME: ClassVar[RuleName] = RuleName('empty-line')
    LEVEL: ClassVar[Level] = Level.ALLOW
    SINCE: ClassVar[Release] = Release('1.0.0')

    def message(self) -> str:
        """Name the condition."""
        return 'line is empty'

    @classmethod
    def check(cls, subject: SampleLines) -> tuple[Self, ...]:
        """Every empty line.

        Args:
            subject: The lines judged.
        """
        return tuple(
            cls(spec=None, line=LineNumber.from_int(index + 1)) for index, line in enumerate(subject.lines) if not line
        )
