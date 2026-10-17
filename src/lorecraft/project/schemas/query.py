"""What a query reads and what it is: a pure function over the primitives of one item.

A query is a plain function from `Primitives` to the fact it derives, such as `title_constraints`. A rule declares the
queries it needs and a database memoizes each by the function and the item. The primitives are the only way a query
reaches the model, so what a query read is what its answer depends on: a database can keep the answer for the next
revision whenever every primitive it read is kept, and a query never reads the snapshot.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from lorecraft.project.syntax import Heading

from .structure import StructureSpec


class Primitives(Protocol):
    """The model state of one item a query derives from; each method is one primitive."""

    def structure_specs(self) -> tuple[StructureSpec, ...]:
        """The structure specifications that govern the item, in the order they apply; none when nothing governs it."""
        ...

    def headings(self) -> tuple[Heading, ...]:
        """The headings of the item's parse, in document order."""
        ...


type Query[T] = Callable[[Primitives], T]


@dataclass(frozen=True, slots=True)
class StructurePrimitives:
    """Primitives that hold the structure specifications as given, for a caller that has no database.

    Attributes:
        specs: The structure specifications that govern the item, in the order they apply.
        heading_list: The headings of the item's parse, in document order.
    """

    specs: tuple[StructureSpec, ...]
    heading_list: tuple[Heading, ...] = ()

    def structure_specs(self) -> tuple[StructureSpec, ...]:
        """The specifications this was built with."""
        return self.specs

    def headings(self) -> tuple[Heading, ...]:
        """The headings this was built with."""
        return self.heading_list
