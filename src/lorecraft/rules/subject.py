"""The query-backed rules over items and layout subjects, with their closed eligibility gates.

Every rule over an item derives from `QueriedItemRule[Facts]`, names its `ItemQuery[Facts]`, and declares a `GATES`
mapping for the item kinds it judges. `ByMetaSpec` requires a loaded structure layer to state the named part;
`ByPackage` admits a package-governed kind, and `BySchema` admits a kind only when the named schema is registered.
A kind absent from the mapping is inapplicable. These declarations let the runner and rule table use one explicit
contract while the rule itself judges only query facts.

A layout entry is not an item: `SymlinkRule` covers links in the skill layout and `CorpusDirectoryRule` covers
reserved-corpus directories. They derive from `LayoutRule`, and their queried forms keep separate primitive and query
types, since an occurrence points at the entry itself and not at a line of Markdown.

Rules in each group declare their own gates alongside their codes and queries. Shared document and skill-entry rules
name both kinds explicitly; Markdown checks can combine structure gates for corpus items with package gates for skill
files, and schema-dependent skill checks name their registered schema directly.
"""

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import ClassVar, Self

from lorecraft.project.item import ItemKind, MetaSpecPart
from lorecraft.project.query import CorpusDirectoryPrimitives, ItemPrimitives, ItemQuery, Query, SymlinkPrimitives
from lorecraft.schemas.types import SchemaReference

from .declaration import ContentRule, LayoutRule, Rule


@dataclass(frozen=True, slots=True)
class ByMetaSpec:
    """A gate for a meta spec part a loaded structure layer may govern.

    Attributes:
        part: The meta spec part a loaded structure layer must state for the rule to judge the item.
        requires_loaded_layer: Whether a skill entry also requires loaded corpus governance for this rule.
    """

    part: MetaSpecPart
    requires_loaded_layer: bool = False


@dataclass(frozen=True, slots=True)
class ByPackage:
    """A gate for an item kind governed independently of a structure layer."""


@dataclass(frozen=True, slots=True)
class BySchema:
    """A gate for an item kind when its governing schema is registered.

    Attributes:
        schema: The registered schema that governs the item for this rule.
    """

    schema: SchemaReference


type Gate = ByMetaSpec | ByPackage | BySchema


@dataclass(frozen=True, slots=True, kw_only=True)
class ItemRule(ContentRule):
    """The base of every rule over an item, with its required per-kind gate mapping.

    Attributes:
        GATES: The item kinds a rule judges and the gate that admits each kind.
    """

    GATES: ClassVar[Mapping[ItemKind, Gate]] = MappingProxyType({})


type SubjectQuery[Facts] = (
    Query[ItemPrimitives, Facts] | Query[SymlinkPrimitives, Facts] | Query[CorpusDirectoryPrimitives, Facts]
)


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
class QueriedItemRule[Facts](Queried[Facts, ItemQuery[Facts]], ItemRule):
    """The base of a rule over items that declares each kind and gate it judges.

    The rule names its query and declares its complete `GATES` mapping. Item kinds absent from that mapping are
    never judged. Layout rules use their separate queried bases because their query primitives differ.
    """

    @classmethod
    @abstractmethod
    def query(cls) -> ItemQuery[Facts]:
        """The query over an item's primitives whose answer `judge` takes."""


@dataclass(frozen=True, slots=True, kw_only=True)
class SymlinkRule(LayoutRule):
    """The base of every rule over a skill-layout symlink; it is package-governed and has no gates."""


@dataclass(frozen=True, slots=True, kw_only=True)
class CorpusDirectoryRule(LayoutRule):
    """The base of every rule over a reserved-corpus directory; it is package-governed and has no gates."""


@dataclass(frozen=True, slots=True, kw_only=True)
class QueriedSymlinkRule[Facts](Queried[Facts, Query[SymlinkPrimitives, Facts]], SymlinkRule):
    """The base of a query-backed rule over a symlink of the skill layout."""

    @classmethod
    @abstractmethod
    def query(cls) -> Query[SymlinkPrimitives, Facts]:
        """The query over a symlink's model state whose answer `judge` takes."""


@dataclass(frozen=True, slots=True, kw_only=True)
class QueriedCorpusDirectoryRule[Facts](Queried[Facts, Query[CorpusDirectoryPrimitives, Facts]], CorpusDirectoryRule):
    """The base of a query-backed rule over a reserved-corpus directory."""

    @classmethod
    @abstractmethod
    def query(cls) -> Query[CorpusDirectoryPrimitives, Facts]:
        """The query over a reserved-corpus directory's model state whose answer `judge` takes."""
