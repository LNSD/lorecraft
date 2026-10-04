"""Input bases for the sample rules the unit tests declare, standing in for the engine's input kinds.

A rule picks its input by deriving from its input's base, whose abstract `check` fixes the input's type. These two
stand in for a subject with lines and a layout entry, so the tests of a rule's declaration and of the registry
depend on no input kind of the engine's.
"""

from abc import abstractmethod
from dataclasses import dataclass
from typing import Self

from ..rule import ContentRule, LayoutRule


@dataclass(frozen=True, slots=True)
class SampleLines:
    """The lines of a sample subject.

    Attributes:
        lines: The subject's lines, the first at index 0.
    """

    lines: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SampleEntry:
    """A sample layout entry: a name and nothing else."""

    name: str


@dataclass(frozen=True, slots=True, kw_only=True)
class SampleLinesRule(ContentRule):
    """The base of every sample rule over the lines of a subject."""

    @classmethod
    @abstractmethod
    def check(cls, subject: SampleLines) -> tuple[Self, ...]:
        """Every occurrence of the rule's condition in the subject's lines.

        Args:
            subject: The lines judged.
        """


@dataclass(frozen=True, slots=True, kw_only=True)
class SampleEntryRule(LayoutRule):
    """The base of every sample rule over a layout entry."""

    @classmethod
    @abstractmethod
    def check(cls, subject: SampleEntry) -> tuple[Self, ...]:
        """The rule's occurrence at the entry, if it has one.

        Args:
            subject: The entry judged.
        """
