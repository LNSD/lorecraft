"""A sample engine condition that declares no severity."""

from dataclasses import dataclass
from typing import ClassVar

from lorecraft.rules.collector import rule
from lorecraft.rules.declaration import EntryCondition
from lorecraft.rules.identity import EngineCode, Release, RuleName
from lorecraft.rules.location import WholeSubject


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class Unsevere(EntryCondition):
    """A sample condition that leaves `SEVERITY` unbound."""

    CODE: ClassVar[EngineCode] = EngineCode(93)
    NAME: ClassVar[RuleName] = RuleName('unsevere')
    SINCE: ClassVar[Release] = Release('1.0.0')

    def message(self) -> str:
        """Name the condition."""
        return 'never reported'

    def primary(self) -> WholeSubject:
        """The whole subject."""
        return WholeSubject()
