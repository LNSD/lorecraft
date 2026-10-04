"""A sample engine condition that declares no severity."""

from dataclasses import dataclass
from typing import ClassVar

from lorecraft.rules.declaration import EngineCondition, Release, RuleCode, RuleName, rule
from lorecraft.rules.engine.__ruleset__ import GROUP_ID
from lorecraft.rules.location import WholeSubject


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class Unsevere(EngineCondition):
    """A sample condition that leaves `SEVERITY` unbound."""

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 903)
    NAME: ClassVar[RuleName] = RuleName('unsevere')
    SINCE: ClassVar[Release] = Release('1.0.0')

    def message(self) -> str:
        """Name the condition."""
        return 'never reported'

    def primary(self) -> WholeSubject:
        """The whole subject."""
        return WholeSubject()
