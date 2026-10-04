"""Two sample rules whose groups share a prefix but not a title."""

from dataclasses import dataclass
from typing import ClassVar, Final, Self

from lorecraft.rules.rule import Level, Release, RuleCode, RuleGroup, RuleName, rule
from lorecraft.rules.tests.sample_input import SampleLines, SampleLinesRule

from ..groups import SAMPLE

RETITLED: Final[RuleGroup] = RuleGroup(SAMPLE.prefix, 'Sample rules under another title')
"""A second group declared with the prefix of `SAMPLE`."""


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class Titled(SampleLinesRule):
    """A sample rule that never fires, in the group `SAMPLE`."""

    CODE: ClassVar[RuleCode] = RuleCode(SAMPLE, 1)
    NAME: ClassVar[RuleName] = RuleName('titled')
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
@dataclass(frozen=True, slots=True, kw_only=True)
class Retitled(SampleLinesRule):
    """A sample rule that never fires, in the group `RETITLED`."""

    CODE: ClassVar[RuleCode] = RuleCode(RETITLED, 2)
    NAME: ClassVar[RuleName] = RuleName('retitled')
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
