"""What a query reads and what it is: a pure function over the primitives of one item.

A query is a plain function from `Primitives` to the fact it derives, such as `title_constraints`. A rule declares the
queries it needs and a database memoizes each by the function and the item. The primitives are the only way a query
reaches the model, so what a query read is what its answer depends on: a database can keep the answer for the next
revision whenever every primitive it read is kept, and a query never reads the snapshot.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Protocol

from lorecraft.core.mapping import FrozenMapping
from lorecraft.core.num import UnsignedInt
from lorecraft.project.link_target import LinkBase, LinkTargetEntry
from lorecraft.project.syntax import Heading, LineCount, Link, NormalisedLinkPath, TokenCount

from .structure import StructureSpec

type Query[T] = Callable[[Primitives], T]


class Primitives(Protocol):
    """The model state of one item a query derives from; each method is one primitive."""

    def structure_specs(self) -> tuple[StructureSpec, ...]:
        """The structure specifications that govern the item, in the order they apply; none when nothing governs it."""
        ...

    def headings(self) -> tuple[Heading, ...]:
        """The headings of the item's parse, in document order."""
        ...

    def token_count(self) -> TokenCount:
        """The tokens in the item's whole file; none for an item that is not UTF-8."""
        ...

    def line_count(self) -> LineCount:
        """The lines in the item's whole file; none for an item that is not UTF-8."""
        ...

    def links(self) -> tuple[Link, ...]:
        """The links of the item's parse, in document order; none for an item that is not UTF-8."""
        ...

    def link_targets(self) -> Mapping[NormalisedLinkPath, LinkTargetEntry]:
        """What the snapshot holds at the target of each relative link; none for an item that is not UTF-8."""
        ...

    def link_base(self) -> LinkBase | None:
        """Where the item's relative links are read from; `None` for an item that is not UTF-8."""
        ...

    def document_name(self) -> str | None:
        """The stem of a document or meta specification; `None` for any other item."""
        ...

    def query[T](self, query: Query[T]) -> T:
        """The memoized answer of another query over the same item, whose reads count as the asking query's own."""
        ...


@dataclass(frozen=True, slots=True)
class StructurePrimitives:
    """Primitives that hold the structure specifications as given, for a caller that has no database.

    Attributes:
        specs: The structure specifications that govern the item, in the order they apply.
        heading_list: The headings of the item's parse, in document order.
        token_total: The tokens in the item's whole file.
        link_list: The links of the item's parse, in document order.
        target_map: What the snapshot holds at the target of each relative link.
        base: Where the item's relative links are read from.
        name: The filename stem of the document.
        line_total: The lines in the item's whole file.
    """

    specs: tuple[StructureSpec, ...]
    heading_list: tuple[Heading, ...] = ()
    token_total: TokenCount = TokenCount(UnsignedInt(0))
    link_list: tuple[Link, ...] = ()
    target_map: Mapping[NormalisedLinkPath, LinkTargetEntry] = FrozenMapping({})
    base: LinkBase | None = None
    name: str | None = None
    line_total: LineCount = LineCount(UnsignedInt(0))

    def structure_specs(self) -> tuple[StructureSpec, ...]:
        """The specifications this was built with."""
        return self.specs

    def headings(self) -> tuple[Heading, ...]:
        """The headings this was built with."""
        return self.heading_list

    def token_count(self) -> TokenCount:
        """The count this was built with."""
        return self.token_total

    def links(self) -> tuple[Link, ...]:
        """The links this was built with."""
        return self.link_list

    def link_targets(self) -> Mapping[NormalisedLinkPath, LinkTargetEntry]:
        """The targets this was built with."""
        return self.target_map

    def link_base(self) -> LinkBase | None:
        """The base this was built with."""
        return self.base

    def document_name(self) -> str | None:
        """The name this was built with."""
        return self.name

    def line_count(self) -> LineCount:
        """The count this was built with."""
        return self.line_total

    def query[T](self, query: Query[T]) -> T:
        """The answer of the query over these same primitives."""
        return query(self)
