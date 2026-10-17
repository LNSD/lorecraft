"""The primitives a query reads, in the facets of the model state they come from.

A primitive is one method; the facets group them by what they answer about an item, so a caller that needs only one
kind of state can name that facet. `Primitives` is the whole, composed from the facets and the memoized `query`.
"""

from collections.abc import Callable, Mapping
from typing import Protocol

from lorecraft.project.link_target import DocumentLink, LinkBase, LinkTargetEntry
from lorecraft.project.schemas import FrontmatterOwner, SchemaProblems, SkillFields, StructureSpec
from lorecraft.project.syntax import (
    Anchor,
    FrontmatterNode,
    Heading,
    LineCount,
    Link,
    NormalisedLinkPath,
    TokenCount,
)

type Query[T] = Callable[[Primitives], T]


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

    def schema_problems(self) -> tuple[SchemaProblems, ...]:
        """What each frontmatter schema that governs the item rejects in its frontmatter, each problem on its line.

        One entry per schema, in the order the schemas apply; none when no schema governs the item, or when its block
        is missing, not YAML or not a mapping, which no schema can hold.
        """
        ...

    def skill_fields(self) -> SkillFields:
        """The fields of a skill entry's frontmatter that parse, each on its own, by the field.

        A field that is not written, is null or is rejected has no entry; none holds for any other item, or when the
        block is missing, not YAML or not a mapping.
        """
        ...

    def frontmatter_owner(self) -> FrontmatterOwner:
        """The document or the skill the block opens, with the name its frontmatter must carry.

        Only a document whose corpus states a structure specification, or a skill entry, has one.
        """
        ...

    def document_name(self) -> str | None:
        """The stem of a document or meta specification; `None` for any other item."""
        ...

    def document_corpus(self) -> str | None:
        """The corpus a document lies in; `None` for any other item or one that is not UTF-8."""
        ...

    def document_base(self) -> str | None:
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

    def document_links(self) -> tuple[DocumentLink, ...]:
        """The links to another document, with its corpus and filename and whether it links back, in document order.

        None for an item that is not UTF-8.
        """
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
