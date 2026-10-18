"""The primitives a query reads, in the facets of the model state they come from.

A primitive is one method; the facets group them by what they answer about an item, so a caller that needs only one
kind of state can name that facet. `Primitives` is the whole, composed from the facets and the memoized `query`.
"""

from collections.abc import Callable, Mapping
from typing import Protocol

from lorecraft.project.corpus import CorpusName
from lorecraft.project.corpus.directory import CorpusDirectoryRef
from lorecraft.project.item import ItemOrigin, MarkdownItemRef
from lorecraft.project.link_target import LinkBase, LinkTargetEntry
from lorecraft.project.schemas import StructureSpec
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
from lorecraft.project.workspace import Governance
from lorecraft.vfs import RootExit

type Query[T] = Callable[[Primitives], T]
type SymlinkQuery[T] = Callable[[SymlinkPrimitives], T]
type CorpusDirectoryQuery[T] = Callable[[CorpusDirectoryPrimitives], T]
type SymlinkQueryRead = tuple[SymlinkQuery[object], SymlinkRef]
type CorpusDirectoryQueryRead = tuple[CorpusDirectoryQuery[object], CorpusDirectoryRef]


class SyntaxPrimitives(Protocol):
    """What the item's parse holds: its headings, anchors, links and frontmatter block."""

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


class CountPrimitives(Protocol):
    """What is measured of the item's whole file."""

    def token_count(self) -> TokenCount:
        """The tokens in the item's whole file; none for an item that is not UTF-8."""
        ...

    def line_count(self) -> LineCount:
        """The lines in the item's whole file; none for an item that is not UTF-8."""
        ...


class GovernancePrimitives(Protocol):
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

    def builtin_skills_schema(self) -> bool:
        """Whether the package's Agent Skills frontmatter schema is enabled for skill entries."""
        ...

    def item_name(self) -> str | None:
        """The stem of a document or meta specification; `None` for any other item."""
        ...

    def item_corpus(self) -> str | None:
        """The corpus a document lies in; `None` for any other item or one that is not UTF-8."""
        ...

    def item_base(self) -> str | None:
        """The stem of the document or specification the item extends, looked for among the names the model lists.

        A document's base is the narrowest document of its corpus whose name its own continues after a hyphen, a
        specification's the narrowest specification; `None` when it has none, and for any other item.
        """
        ...


class LinkResolutionPrimitives(Protocol):
    """What the snapshot holds where the item's links point."""

    def link_targets(self) -> Mapping[NormalisedLinkPath, LinkTargetEntry]:
        """What the snapshot holds at the target of each relative link; none for an item that is not UTF-8."""
        ...

    def link_base(self) -> LinkBase | None:
        """Where the item's relative links are read from; `None` for an item that is not UTF-8."""
        ...


class Primitives(
    SyntaxPrimitives,
    CountPrimitives,
    GovernancePrimitives,
    LinkResolutionPrimitives,
    Protocol,
):
    """The model state of one item a query derives from; each method is one primitive, grouped in the facets."""

    def query[T](self, query: Query[T]) -> T:
        """The memoized answer of another query over the same item, whose reads count as the asking query's own."""
        ...

    def query_at[T](self, ref: MarkdownItemRef, query: Query[T]) -> T:
        """The memoized answer of a query over another item, recorded as the typed pair `(query, ref)`.

        Args:
            ref: The item whose primitives the query reads.
            query: The pure function to run over that item's primitives.
        """
        ...


class SymlinkPrimitives(Protocol):
    """The model state of one symlink of the skill layout whose chain leaves the repository."""

    def leaves_at(self) -> RootExit:
        """The link the symlink's chain leaves the repository through, and its target, as the scan recorded it."""
        ...


class CorpusDirectoryPrimitives(Protocol):
    """The model state of one directory under `docs/` that takes a reserved corpus's name."""

    def reserved_corpus(self) -> CorpusName:
        """The reserved corpus whose name the directory takes."""
        ...
