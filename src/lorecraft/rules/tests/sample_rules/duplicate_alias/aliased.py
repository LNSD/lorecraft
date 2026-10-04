"""Two sample rules that answer to one upstream code."""

from dataclasses import dataclass
from typing import ClassVar, Self

from lorecraft.rules.declaration import AliasCode, Level, Release, RuleCode, RuleName, rule
from lorecraft.rules.tests.sample_input import SampleLines, SampleLinesRule

from ..groups import SAMPLE


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class FirstAliased(SampleLinesRule):
    """A sample rule that never fires."""

    CODE: ClassVar[RuleCode] = RuleCode(SAMPLE, 1)
    NAME: ClassVar[RuleName] = RuleName('first-aliased')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('1.0.0')
    ALIASES: ClassVar[tuple[AliasCode, ...]] = (AliasCode('markdownlint', 'MD009'),)

    def message(self) -> str:
        """Name the condition."""
        return 'never reported'

    @classmethod
    def check(cls, subject: SampleLines) -> tuple[Self, ...]:
        """No occurrence, whatever the lines.

        Args:
            subject: The lines judged.
        """
        return ()


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class SecondAliased(SampleLinesRule):
    """A sample rule that never fires."""

    CODE: ClassVar[RuleCode] = RuleCode(SAMPLE, 2)
    NAME: ClassVar[RuleName] = RuleName('second-aliased')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('1.0.0')
    ALIASES: ClassVar[tuple[AliasCode, ...]] = (AliasCode('markdownlint', 'MD009'),)

    def message(self) -> str:
        """Name the condition."""
        return 'never reported'

    @classmethod
    def check(cls, subject: SampleLines) -> tuple[Self, ...]:
        """No occurrence, whatever the lines.

        Args:
            subject: The lines judged.
        """
        return ()
