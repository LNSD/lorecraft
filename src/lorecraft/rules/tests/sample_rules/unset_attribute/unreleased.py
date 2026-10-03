"""A sample rule that declares no release it is stable since."""

from dataclasses import dataclass
from typing import ClassVar, Self

from lorecraft.rules.rule import Level, RuleCode, rule
from lorecraft.rules.tests.sample_input import SampleLines, SampleLinesRule

from ..groups import SAMPLE


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class Unreleased(SampleLinesRule):
    """A sample rule that never fires, and leaves `SINCE` unbound."""

    CODE: ClassVar[RuleCode] = RuleCode(SAMPLE, 1)
    NAME: ClassVar[str] = 'unreleased'
    LEVEL: ClassVar[Level] = Level.DENY

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
