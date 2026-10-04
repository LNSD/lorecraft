"""A sample engine condition declared without its message."""

from dataclasses import dataclass
from typing import ClassVar

from lorecraft.rules.declaration import EngineCondition, Release, RuleCode, RuleName, Severity, rule
from lorecraft.rules.engine.__ruleset__ import GROUP_ID
from lorecraft.rules.location import WholeSubject


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class Unworded(EngineCondition):
    """A sample condition that cannot be reported: it does not implement `message`."""

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 904)
    NAME: ClassVar[RuleName] = RuleName('unworded')
    SINCE: ClassVar[Release] = Release('1.0.0')
    SEVERITY: ClassVar[Severity] = Severity.ERROR

    def primary(self) -> WholeSubject:
        """The whole subject."""
        return WholeSubject()
