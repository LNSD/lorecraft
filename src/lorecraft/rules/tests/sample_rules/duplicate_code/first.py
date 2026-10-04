"""A sample rule declared with the code `SMP001`."""

from dataclasses import dataclass
from typing import ClassVar, Self

from lorecraft.rules.declaration import Level, Release, RuleCode, RuleName, rule
from lorecraft.rules.tests.sample_input import SampleLines, SampleLinesRule

from ..groups import SAMPLE


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class FirstRule(SampleLinesRule):
    """A sample rule that never fires."""

    CODE: ClassVar[RuleCode] = RuleCode(SAMPLE, 1)
    NAME: ClassVar[RuleName] = RuleName('first-rule')
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
