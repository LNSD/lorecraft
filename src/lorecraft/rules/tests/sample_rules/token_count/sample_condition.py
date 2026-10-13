"""A sample engine condition, in the engine's group, which no rule table ever holds."""

from dataclasses import dataclass
from typing import ClassVar

from lorecraft.rules.declaration import EngineCode, EntryCondition, Release, RuleName, Severity, rule
from lorecraft.rules.location import WholeSubject


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class SampleCondition(EntryCondition):
    """A sample condition the engine would report about a whole subject."""

    CODE: ClassVar[EngineCode] = EngineCode(900)
    NAME: ClassVar[RuleName] = RuleName('sample-condition')
    SINCE: ClassVar[Release] = Release('1.0.0')
    SEVERITY: ClassVar[Severity] = Severity.WARNING

    def message(self) -> str:
        """Name the condition."""
        return 'sample condition'

    def primary(self) -> WholeSubject:
        """The whole subject."""
        return WholeSubject()
