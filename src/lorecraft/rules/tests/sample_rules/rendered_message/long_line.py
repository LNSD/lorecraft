"""A sample rule whose message names a value it captured: a line is longer than 80 characters."""

from dataclasses import dataclass
from typing import ClassVar, Self

from lorecraft.project.syntax import LineNumber
from lorecraft.rules.declaration import Level, Release, RuleCode, RuleName, rule
from lorecraft.rules.tests.sample_input import SampleLines, SampleLinesRule

from ..groups import SAMPLE


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class LongLine(SampleLinesRule):
    """A line is longer than 80 characters.

    Attributes:
        length: The line's length, in characters.
    """

    CODE: ClassVar[RuleCode] = RuleCode(SAMPLE, 3)
    NAME: ClassVar[RuleName] = RuleName('long-line')
    LEVEL: ClassVar[Level] = Level.WARN
    SINCE: ClassVar[Release] = Release('1.0.0')

    length: int

    def message(self) -> str:
        """Name the condition and the line's length."""
        return f'line is {self.length} characters long'

    @classmethod
    def check(cls, subject: SampleLines) -> tuple[Self, ...]:
        """Every line longer than 80 characters.

        Args:
            subject: The lines judged.
        """
        return tuple(
            cls(spec=None, line=LineNumber.parse(index + 1), length=len(line))
            for index, line in enumerate(subject.lines)
            if len(line) > 80
        )
