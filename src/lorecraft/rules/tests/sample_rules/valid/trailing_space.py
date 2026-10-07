"""A sample rule with an alias code: a line ends in a space."""

from dataclasses import dataclass
from typing import ClassVar, Self

from lorecraft.project.syntax import LineNumber
from lorecraft.rules.declaration import AliasCode, Level, LinterName, Release, RuleCode, RuleName, UpstreamCode, rule
from lorecraft.rules.tests.sample_subject import SampleLines, SampleLinesRule

from ..groups import SAMPLE


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class TrailingSpace(SampleLinesRule):
    """A line ends in a space."""

    CODE: ClassVar[RuleCode] = RuleCode(SAMPLE, 2)
    NAME: ClassVar[RuleName] = RuleName('trailing-space')
    LEVEL: ClassVar[Level] = Level.WARN
    SINCE: ClassVar[Release] = Release('1.2.0')
    ALIASES: ClassVar[tuple[AliasCode, ...]] = (AliasCode(LinterName('markdownlint'), UpstreamCode('MD009')),)

    def message(self) -> str:
        """Name the condition."""
        return 'line ends in a space'

    @classmethod
    def check(cls, subject: SampleLines) -> tuple[Self, ...]:
        """Every line that ends in a space.

        Args:
            subject: The lines judged.
        """
        return tuple(
            cls(spec=None, line=LineNumber.from_int(index + 1))
            for index, line in enumerate(subject.lines)
            if line.endswith(' ')
        )
