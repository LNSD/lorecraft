"""A sample rule over a layout entry: its name holds an uppercase letter."""

from dataclasses import dataclass
from typing import ClassVar, Self

from lorecraft.rules.rule import Level, Release, RuleCode
from lorecraft.rules.tests.sample_input import SampleEntry, SampleEntryRule

from ..groups import LAYOUT


@dataclass(frozen=True, slots=True, kw_only=True)
class UppercaseEntry(SampleEntryRule):
    """A layout entry's name holds an uppercase letter."""

    CODE: ClassVar[RuleCode] = RuleCode(LAYOUT, 1)
    NAME: ClassVar[str] = 'uppercase-entry'
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('1.0.0')

    def message(self) -> str:
        """Name the condition."""
        return 'entry name holds an uppercase letter'

    @classmethod
    def check(cls, subject: SampleEntry) -> tuple[Self, ...]:
        """The occurrence at the entry, when its name is not all lowercase.

        Args:
            subject: The entry judged.
        """
        if subject.name == subject.name.lower():
            return ()
        return (cls(spec=None),)
