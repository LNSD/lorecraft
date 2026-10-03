"""A sample rule and a sample removed rule, declared with one name."""

from dataclasses import dataclass
from typing import ClassVar, Self

from lorecraft.rules.rule import Level, Release, RemovedRule, RuleCode, rule
from lorecraft.rules.tests.sample_input import SampleLines, SampleLinesRule

from ..groups import SAMPLE


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class InService(SampleLinesRule):
    """A sample rule that never fires."""

    CODE: ClassVar[RuleCode] = RuleCode(SAMPLE, 1)
    NAME: ClassVar[str] = 'shared-name'
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


@rule
class Retired(RemovedRule):
    """A sample removed rule that kept its name for a rule in service."""

    CODE: ClassVar[RuleCode] = RuleCode(SAMPLE, 2)
    NAME: ClassVar[str] = 'shared-name'
    REMOVED_IN: ClassVar[Release] = Release('1.1.0')
    REPLACED_BY: ClassVar[RuleCode | None] = None
