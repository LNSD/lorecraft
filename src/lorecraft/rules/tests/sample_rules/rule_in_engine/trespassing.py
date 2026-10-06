"""A sample rule declared with a code in the engine's group."""

from dataclasses import dataclass
from typing import ClassVar, Self

from lorecraft.rules.declaration import Level, Release, RuleCode, RuleName, rule
from lorecraft.rules.engine.__ruleset__ import GROUP_ID
from lorecraft.rules.tests.sample_subject import SampleLines, SampleLinesRule


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class Trespassing(SampleLinesRule):
    """A sample rule that never fires, in the group reserved for engine conditions."""

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 901)
    NAME: ClassVar[RuleName] = RuleName('trespassing')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('1.0.0')

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
