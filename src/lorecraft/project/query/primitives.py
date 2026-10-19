"""The primitives a query reads, in the facets of the model state they come from.

A primitive is one method; the facets group them by what they answer about an item, so a caller that needs only one
kind of state can name that facet. `Primitives` is the whole, composed from the facets and the memoized `query`.
Schema subjects have their own parameterless query family over immutable inputs retained by the workspace model.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Protocol

from lorecraft.project.aspect import AspectFilename
from lorecraft.project.corpus import CorpusName
from lorecraft.project.corpus.directory import CorpusDirectoryRef
from lorecraft.project.item import ItemOrigin, MarkdownItemDescriptor, MarkdownItemRef
from lorecraft.project.link_target import LinkBase, LinkTargetEntry
from lorecraft.project.skill.outside import SymlinkRef
from lorecraft.project.syntax import (
    Anchor,
    FrontmatterNode,
    Heading,
    LineCount,
    Link,
    NormalisedLinkPath,
    TokenCount,
)
from lorecraft.schemas import SchemaInput, SchemaReference
from lorecraft.vfs import RootExit

if TYPE_CHECKING:
    from lorecraft.project.schemas.name import SpecName
    from lorecraft.project.schemas.structure import StructureSpec
    from lorecraft.project.workspace import Governance

type Query[T] = Callable[[Primitives], T]
type SameSubjectQuery[P, T] = Callable[[P], T]
type SymlinkQuery[T] = Callable[[SymlinkPrimitives], T]
type CorpusDirectoryQuery[T] = Callable[[CorpusDirectoryPrimitives], T]
type SchemaQuery[T] = Callable[[SchemaPrimitives], T]
type SubjectRef = MarkdownItemRef | SymlinkRef | CorpusDirectoryRef | SchemaReference
type SubjectQuery[T] = Query[T] | SymlinkQuery[T] | CorpusDirectoryQuery[T] | SchemaQuery[T]


class QueryPrimitives[P](Protocol):
    """Same-subject query operations shared by every subject's primitive facet."""

    def query[T](self, query: SameSubjectQuery[P, T]) -> T:
        """Read a query over the same subject and record its dependency."""
        ...


class ItemReads(Protocol):
    """Cross-subject queries whose target is a Markdown item."""

    def query_at[T](self, ref: MarkdownItemRef, query: Query[T]) -> T:
        """Read an item query by reference and record the typed dependency."""
        ...


class SchemaReads(Protocol):
    """Cross-subject queries whose target is a schema."""

    def query_schema[T](self, ref: SchemaReference, query: SchemaQuery[T]) -> T:
        """Read a schema query by reference and record the typed dependency."""
        ...


class DecodedText(Protocol):
    """The raw text facts every decoded item witness exposes to a query."""

    descriptor: MarkdownItemDescriptor
    text: str


class SchemaPrimitives(QueryPrimitives['SchemaPrimitives'], SchemaReads, Protocol):
    """The immutable input for one typed schema subject."""

    def schema_input(self) -> SchemaInput:
        """The loaded schema input identified by this query's subject reference."""
        ...


class SyntaxPrimitives(QueryPrimitives['Primitives'], Protocol):
    """What the item's parse holds: its headings, anchors, links and frontmatter block."""

    def item_text(self) -> DecodedText | None:
        """The decoded witness of this subject, or none when its bytes are not UTF-8."""
        ...

    def headings(self) -> tuple[Heading, ...]:
        """The headings of the item's parse, in document order."""
        ...

    def links(self) -> tuple[Link, ...]:
        """The links of the item's parse, in document order; none for an item that is not UTF-8."""
        ...

    def anchors(self) -> frozenset[Anchor]:
        """The anchor of every heading of the item's parse, as GitHub derives them; none for a non-UTF-8 item."""
        ...

    def frontmatter(self) -> FrontmatterNode:
        """The item's frontmatter block as parsed: missing, not YAML, not a mapping, or the mapping."""
        ...


class CountPrimitives(QueryPrimitives['Primitives'], Protocol):
    """What is measured of the item's whole file."""

    def token_count(self) -> TokenCount:
        """The tokens in the item's whole file; none for an item that is not UTF-8."""
        ...

    def line_count(self) -> LineCount:
        """The lines in the item's whole file; none for an item that is not UTF-8."""
        ...


class GovernancePrimitives(QueryPrimitives['Primitives'], Protocol):
    """What governs the item and what it is named: its specifications, schemas, owner and place among the documents."""

    def structure_specs(self) -> tuple[StructureSpec, ...]:
        """The structure specifications that govern the item, in the order they apply; none when nothing governs it."""
        ...

    def item_origin(self) -> ItemOrigin:
        """The model's origin facts for this item, including its expected name and provenance."""
        ...

    def item_governance(self) -> Governance | None:
        """The governance of this item, or none when it has no corpus governance."""
        ...

    def item_name(self) -> AspectFilename | SpecName | None:
        """The typed name of a document or meta specification; `None` for any other item."""
        ...

    def item_corpus(self) -> CorpusName | None:
        """The typed corpus a document lies in; `None` for any other item or one that is not UTF-8."""
        ...

    def item_base(self) -> AspectFilename | SpecName | None:
        """The typed name of the document or specification the item extends, looked for among the names the model lists.

        A document's base is the narrowest document of its corpus whose name its own continues after a hyphen, a
        specification's the narrowest specification; `None` when it has none, and for any other item.
        """
        ...


class TitlePrimitives(SyntaxPrimitives, GovernancePrimitives, Protocol):
    """The syntax and structure facets used to derive document title facts."""


class LinkResolutionPrimitives(Protocol):
    """What the snapshot holds where the item's links point."""

    def link_targets(self) -> Mapping[NormalisedLinkPath, LinkTargetEntry]:
        """What the snapshot holds at the target of each relative link; none for an item that is not UTF-8."""
        ...

    def link_base(self) -> LinkBase | None:
        """Where the item's relative links are read from; `None` for an item that is not UTF-8."""
        ...


class Primitives(
    ItemReads,
    SchemaReads,
    SyntaxPrimitives,
    CountPrimitives,
    GovernancePrimitives,
    LinkResolutionPrimitives,
    Protocol,
):
    """The model state of one item a query derives from; each method is one primitive, grouped in the facets."""


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
