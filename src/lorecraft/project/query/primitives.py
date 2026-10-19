"""The primitives a query reads, grouped by the model state they come from.

A primitive is one method; protocol groups organize them by what they answer about an item, so a query can declare
the state it needs. `ItemPrimitives` composes those groups with the memoized `query` operation.
Schema subjects have their own parameterless query family over immutable inputs retained by the workspace model.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Protocol

from lorecraft.project.aspect import AspectFilename
from lorecraft.project.corpus import CorpusName
from lorecraft.project.corpus.directory import CorpusDirectoryRef
from lorecraft.project.item import ItemDescriptor, ItemOrigin, ItemRef
from lorecraft.project.link_target import LinkBase, LinkTargetEntry
from lorecraft.project.skill.outside import SymlinkRef
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
type QueryTargetRef = ItemRef | SymlinkRef | CorpusDirectoryRef | SchemaRef
type SubjectQuery[T] = (
    Query[ItemPrimitives, T]
    | Query[SymlinkPrimitives, T]
    | Query[CorpusDirectoryPrimitives, T]
    | Query[SchemaPrimitives, T]
)


class QueryPrimitives[P](Protocol):
    """Same-subject query operations shared by every subject's primitive group."""

    def query[T](self, query: Query[P, T]) -> T:
        """Read a query over the same subject and record its dependency."""
        ...


class ItemReads(Protocol):
    """Cross-subject queries whose target is a Markdown item."""

    def query_at[T](self, ref: ItemRef, query: ItemQuery[T]) -> T:
        """Read an item query by reference and record the typed dependency."""
        ...


class SchemaReads(Protocol):
    """Cross-subject queries whose target is a schema."""

    def query_schema[T](self, ref: SchemaRef, query: Query[SchemaPrimitives, T]) -> T:
        """Read a schema query by reference and record the typed dependency."""
        ...


class DecodedText(Protocol):
    """The raw text state every decoded item witness exposes to a query."""

    descriptor: ItemDescriptor
    text: str


class SchemaPrimitives(QueryPrimitives['SchemaPrimitives'], SchemaReads, Protocol):
    """The immutable input for one typed schema subject."""

    def schema_input(self) -> SchemaInput:
        """The loaded schema input identified by this query's subject reference."""
        ...


class SyntaxPrimitives(QueryPrimitives['ItemPrimitives'], Protocol):
    """Raw decoded text from which syntax and counts are derived."""

    def item_text(self) -> DecodedText | None:
        """The decoded witness of this subject, or none when its bytes are not UTF-8."""
        ...


# Counts are derived from the same raw text witness as syntax.
CountPrimitives = SyntaxPrimitives


class GovernancePrimitives(QueryPrimitives['ItemPrimitives'], Protocol):
    """What governs the item and what it is named: its specifications, schemas, owner and place among the documents."""

    def item_origin(self) -> ItemOrigin:
        """The model's origin metadata for this item, including its expected name and provenance."""
        ...

    def item_governance(self) -> Governance | None:
        """The governance of this item, or none when it has no corpus governance."""
        ...

    def item_base(self) -> AspectFilename | SpecName | None:
        """The typed name of the document or specification the item extends, looked for among the names the model lists.

        A document's base is the narrowest document of its corpus whose name its own continues after a hyphen, a
        specification's the narrowest specification; `None` when it has none, and for any other item.
        """
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
    ItemReads,
    SchemaReads,
    SyntaxPrimitives,
    GovernancePrimitives,
    LinkResolutionPrimitives,
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
