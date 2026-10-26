"""The query-backed rules over items and layout subjects, with their closed eligibility gates.

Every rule over an item derives from `QueriedItemRule[Facts]`, names its `ItemQuery[Facts]`, and declares an
`APPLIES_TO` mapping for the item types it judges. `WhenSpec` requires a loaded layer to state the named part, and
`Always` admits the item type wherever it appears in the rule's mapping.
An item type absent from the mapping is inapplicable. These declarations let the runner and rule table use one explicit
contract while the rule itself judges only query facts.

A layout entry is not an item: `QueriedSymlinkRule` covers links in the skill layout and
`QueriedCorpusDirectoryRule` covers reserved-corpus directories. Their separate primitive and query types preserve
the entry subject, since an occurrence points at the entry itself and not at a line of Markdown.

Rules in each group declare their own applicability alongside their codes and queries. Shared document and skill rules
name both item types explicitly; Markdown checks can combine structure requirements for corpus items with `Always` for
skill files.
"""

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar, Self

from lorecraft.project.item import ItemType, SpecPart
from lorecraft.project.query import (
    CorpusDirectoryQuery,
    ItemQuery,
    SymlinkQuery,
)

from .declaration import ContentRule, LayoutRule, Rule


@dataclass(frozen=True, slots=True)
class WhenSpec:
    """A gate for a spec part a loaded layer may govern.

    Attributes:
        part: The spec part a loaded layer must state for the rule to judge the item.
    """

    part: SpecPart


@dataclass(frozen=True, slots=True)
class Always:
    """A gate for an item type governed independently of a structure layer."""


type Gate = WhenSpec | Always


class Queried[Facts, QueryType](Rule, ABC):
    """The mixin of a rule that names the query it needs and judges its facts.

    The rule names its query in `query` and its `judge` takes the facts that query returns, both typed by the rule's
    type argument: a rule whose query returns `TitleFacts` derives from `QueriedItemRule[TitleFacts]`, and a
    query of another type fails the type check. The runner resolves the query through the database and hands the
    facts to `judge`, so the rule is coupled to the rest only through the model state its query reads.
    """

    __slots__ = ()

    @classmethod
    @abstractmethod
    def query(cls) -> QueryType:
        """The query whose answer `judge` takes; the same function every call, since the database memoizes by it."""

    @classmethod
    @abstractmethod
    def judge(cls, facts: Facts, /) -> tuple[Self, ...]:
        """Every occurrence of the rule's condition, from the facts alone.

        Args:
            facts: The answer of the rule's query.
        """


@dataclass(frozen=True, slots=True, kw_only=True)
class QueriedItemRule[Facts](Queried[Facts, ItemQuery[Facts]], ContentRule):
    """The base of a rule over items that declares each item type and gate it judges.

    The rule names its query and declares its complete `APPLIES_TO` mapping. Item types absent from that mapping are
    never judged. Layout rules use their separate queried bases because their query primitives differ.
    """

    APPLIES_TO: ClassVar[Mapping[ItemType, Gate]]

    @classmethod
    @abstractmethod
    def query(cls) -> ItemQuery[Facts]:
        """The query over an item's primitives whose answer `judge` takes."""


@dataclass(frozen=True, slots=True, kw_only=True)
class QueriedSymlinkRule[Facts](Queried[Facts, SymlinkQuery[Facts]], LayoutRule):
    """The base of a query-backed rule over a symlink of the skill layout."""

    @classmethod
    @abstractmethod
    def query(cls) -> SymlinkQuery[Facts]:
        """The query over a symlink's model state whose answer `judge` takes."""


@dataclass(frozen=True, slots=True, kw_only=True)
class QueriedCorpusDirectoryRule[Facts](Queried[Facts, CorpusDirectoryQuery[Facts]], LayoutRule):
    """The base of a query-backed rule over a reserved-corpus directory."""

    @classmethod
    @abstractmethod
    def query(cls) -> CorpusDirectoryQuery[Facts]:
        """The query over a reserved-corpus directory's model state whose answer `judge` takes."""
