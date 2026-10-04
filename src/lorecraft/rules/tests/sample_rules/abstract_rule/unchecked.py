"""A sample rule declared without its check."""

from dataclasses import dataclass
from typing import ClassVar

from lorecraft.rules.rule import Level, Release, RuleCode, rule
from lorecraft.rules.tests.sample_input import SampleLinesRule

from ..groups import SAMPLE


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class Unchecked(SampleLinesRule):
    """A sample rule that cannot judge anything: it does not implement `check`."""

    CODE: ClassVar[RuleCode] = RuleCode(SAMPLE, 1)
    NAME: ClassVar[str] = 'unchecked'
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('1.0.0')

    def message(self) -> str:
        """Name the condition."""
        return 'never reported'
