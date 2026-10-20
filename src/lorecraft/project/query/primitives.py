"""The primitives a query reads, grouped by the model state they come from.

A primitive is one method; protocol groups organize them by what they answer about an item, so a query can declare
the state it needs. `ItemPrimitives` composes those groups with the memoized `query` operation.
Schema subjects have their own parameterless query family over immutable inputs retained by the workspace model.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, overload

from lorecraft.project.aspect import AspectFilename
from lorecraft.project.corpus import CorpusName
from lorecraft.project.corpus.directory import ReservedCorpusDirectoryRef
from lorecraft.project.item import ItemDescriptor, ItemRef
from lorecraft.project.link_target import LinkBase, LinkTargetEntry
from lorecraft.project.skill.outside import OutsideSymlinkRef
from lorecraft.project.syntax import (
    NormalisedLinkPath,
)
from lorecraft.schemas import SchemaInput, SchemaRef
from lorecraft.vfs import RootExit

if TYPE_CHECKING:
    from lorecraft.project.schemas.name import SpecName
    from lorecraft.project.workspace import Governance

type Query[P, T] = Callable[[P], T]
type ItemQuery[T] = Query[ItemPrimitives, T]
type SymlinkQuery[T] = Query[SymlinkPrimitives, T]
type CorpusDirectoryQuery[T] = Query[CorpusDirectoryPrimitives, T]
type SchemaQuery[T] = Query[SchemaPrimitives, T]
type QueryTargetRef = ItemRef | OutsideSymlinkRef | ReservedCorpusDirectoryRef | SchemaRef
type SubjectQuery[T] = ItemQuery[T] | SymlinkQuery[T] | CorpusDirectoryQuery[T] | SchemaQuery[T]


class QueryPrimitives[P](Protocol):
    """Same-subject and cross-subject queries shared by every primitive group."""

    def query[T](self, query: Query[P, T]) -> T:
        """Read a query over the same subject and record its dependency."""
        ...

    @overload
    def query_at[T](self, ref: ItemRef, query: ItemQuery[T]) -> T: ...

    @overload
    def query_at[T](self, ref: OutsideSymlinkRef, query: SymlinkQuery[T]) -> T: ...

    @overload
    def query_at[T](self, ref: ReservedCorpusDirectoryRef, query: CorpusDirectoryQuery[T]) -> T: ...

    @overload
    def query_at[T](self, ref: SchemaRef, query: SchemaQuery[T]) -> T: ...


class DecodedText(Protocol):
    """The raw text state every decoded item witness exposes to a query."""

    @property
    def text(self) -> str:
        """The decoded file text."""
        ...


@dataclass(frozen=True, slots=True)
class NameHierarchy:
    """The one typed base name an item base query can return."""

    base_name: AspectFilename | SpecName | None = None


class SchemaPrimitives(QueryPrimitives['SchemaPrimitives'], Protocol):
    """The immutable input for one typed schema subject."""

    def schema_input(self) -> SchemaInput:
        """The loaded schema input identified by this query's subject reference."""
        ...


class SyntaxPrimitives(QueryPrimitives['ItemPrimitives'], Protocol):
    """Raw decoded text from which syntax and counts are derived."""

    def text(self) -> DecodedText | None:
        """The decoded witness of this subject, or none when its bytes are not UTF-8."""
        ...


# Counts are derived from the same raw text witness as syntax.
CountPrimitives = SyntaxPrimitives


class GovernancePrimitives(QueryPrimitives['ItemPrimitives'], Protocol):
    """What governs the item and what it is named: its specifications, schemas, owner and place among the documents."""

    def descriptor(self) -> ItemDescriptor:
        """The model-resolved descriptor, the single primitive for descriptor facts."""
        ...

    def governance(self) -> Governance | None:
        """The governance of this item, or none when it has no corpus governance."""
        ...


class NameHierarchyPrimitives(Protocol):
    """The raw descriptor and model hierarchy used to derive an item's base."""

    def text(self) -> DecodedText | None:
        """The decoded witness of this subject, or none when its bytes are not UTF-8."""
        ...

    def descriptor(self) -> ItemDescriptor:
        """The model-resolved raw descriptor of this item."""
        ...

    def name_hierarchy(self) -> NameHierarchy:
        """The name hierarchy used to find this item's declared base."""
        ...


class TitlePrimitives(SyntaxPrimitives, GovernancePrimitives, Protocol):
    """The syntax and structure state used to derive a document's title."""


class LinkResolutionPrimitives(QueryPrimitives['ItemPrimitives'], Protocol):
    """What the snapshot holds where the item's links point."""

    def link_targets(self) -> Mapping[NormalisedLinkPath, LinkTargetEntry]:
        """What the snapshot holds at the target of each relative link; none for an item that is not UTF-8."""
        ...

    def link_base(self) -> LinkBase | None:
        """Where the item's relative links are read from; `None` for an item that is not UTF-8."""
        ...


class ItemPrimitives(
    SyntaxPrimitives,
    GovernancePrimitives,
    NameHierarchyPrimitives,
    LinkResolutionPrimitives,
    QueryPrimitives['ItemPrimitives'],
    Protocol,
):
    """The model state of one item a query derives from, grouped by primitive protocol."""


class SymlinkPrimitives(QueryPrimitives['SymlinkPrimitives'], Protocol):
    """The model state of one symlink of the skill layout whose chain leaves the repository."""

    def leaves_at(self) -> RootExit:
        """The link the symlink's chain leaves the repository through, and its target, as the scan recorded it."""
        ...


class CorpusDirectoryPrimitives(QueryPrimitives['CorpusDirectoryPrimitives'], Protocol):
    """The model state of one directory under `docs/` that takes a reserved corpus's name."""

    def reserved_corpus(self) -> CorpusName:
        """The reserved corpus whose name the directory takes."""
        ...
