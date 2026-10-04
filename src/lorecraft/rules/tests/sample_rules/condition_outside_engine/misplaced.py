"""A sample engine condition declared with a code in a group of rules."""

from dataclasses import dataclass
from typing import ClassVar

from lorecraft.rules.declaration import EngineCondition, Release, RuleCode, RuleName, Severity, rule
from lorecraft.rules.location import WholeSubject

from ..groups import SAMPLE


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class Misplaced(EngineCondition):
    """A sample condition whose code is in the group `SAMPLE`, not the engine's."""

    CODE: ClassVar[RuleCode] = RuleCode(SAMPLE, 1)
    NAME: ClassVar[RuleName] = RuleName('misplaced')
    SINCE: ClassVar[Release] = Release('1.0.0')
    SEVERITY: ClassVar[Severity] = Severity.ERROR

    def message(self) -> str:
        """Name the condition."""
        return 'never reported'

    def primary(self) -> WholeSubject:
        """The whole subject."""
        return WholeSubject()
