"""Subject bases for the sample rules the unit tests declare, standing in for the engine's subject kinds.

A rule picks its subject by deriving from its subject kind's base, whose abstract `judge` takes the facts it reads.
These two stand in for a subject with lines and a layout entry, so the tests of a rule's declaration and of the
registry depend on no subject kind of the engine's. Their `query` is never run: the tests hand `judge` its facts.
"""

from abc import abstractmethod
from dataclasses import dataclass
from typing import NoReturn, Self

from lorecraft.project.query import ItemQuery, Primitives

from ..declaration import ContentRule, LayoutRule
from ..subject import Queried


def _unqueried(primitives: Primitives) -> NoReturn:
    """Stand in for a query, which no test of a sample rule runs."""
    raise NotImplementedError('a sample rule is judged on facts the test hands it')


@dataclass(frozen=True, slots=True)
class SampleLines:
    """The lines of a sample subject.

    Attributes:
        lines: The subject's lines, the first at index 0.
    """

    lines: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SampleEntry:
    """A sample layout entry: a name and nothing else.

    Attributes:
        name: The entry's name, which a sample rule reads and reports.
    """

    name: str


@dataclass(frozen=True, slots=True, kw_only=True)
class SampleLinesRule(Queried[SampleLines, ItemQuery[SampleLines]], ContentRule):
    """The base of every sample rule over the lines of a subject."""

    @classmethod
    def query(cls) -> ItemQuery[SampleLines]:
        """The query a sample rule names; the tests never run it."""
        return _unqueried

    @classmethod
    @abstractmethod
    def judge(cls, facts: SampleLines, /) -> tuple[Self, ...]:
        """Every occurrence of the rule's condition in the subject's lines.

        Args:
            facts: The lines judged.
        """


@dataclass(frozen=True, slots=True, kw_only=True)
class SampleEntryRule(Queried[SampleEntry, ItemQuery[SampleEntry]], LayoutRule):
    """The base of every sample rule over a layout entry."""

    @classmethod
    def query(cls) -> ItemQuery[SampleEntry]:
        """The query a sample rule names; the tests never run it."""
        return _unqueried

    @classmethod
    @abstractmethod
    def judge(cls, facts: SampleEntry, /) -> tuple[Self, ...]:
        """The rule's occurrence at the entry, if it has one.

        Args:
            facts: The entry judged.
        """
