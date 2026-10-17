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
from lorecraft.project.syntax import (
    Anchor,
    FrontmatterNode,
    Heading,
    LineCount,
    Link,
    MissingFrontmatter,
    NormalisedLinkPath,
    TokenCount,
)

from .frontmatter_owner import FrontmatterOwner
from .schema_problems import SchemaProblems
from .skill_fields import SkillFields
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

    def anchors(self) -> frozenset[Anchor]:
        """The anchor of every heading of the item's parse, as GitHub derives them; none for a non-UTF-8 item."""
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

    def document_base(self) -> str | None:
        """The stem of the document or specification the item extends, looked for among the names the model lists.

        A document's base is the narrowest document of its corpus whose name its own continues after a hyphen, a
        specification's the narrowest specification; `None` when it has none, and for any other item.
        """
        ...

    def frontmatter(self) -> FrontmatterNode:
        """The item's frontmatter block as parsed: missing, not YAML, not a mapping, or the mapping."""
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
        frontmatter_node: The item's frontmatter block as parsed.
        problems: What each frontmatter schema that governs the item rejects, in the order the schemas apply.
        fields: The fields of a skill entry's frontmatter that parse.
        owner: Whose frontmatter block it is, when the item has an owner.
        anchor_set: The anchor of every heading of the item's parse.
        base_name: The stem of the document the document extends.
    """

    specs: tuple[StructureSpec, ...]
    heading_list: tuple[Heading, ...] = ()
    token_total: TokenCount = TokenCount(UnsignedInt(0))
    link_list: tuple[Link, ...] = ()
    target_map: Mapping[NormalisedLinkPath, LinkTargetEntry] = FrozenMapping({})
    base: LinkBase | None = None
    name: str | None = None
    line_total: LineCount = LineCount(UnsignedInt(0))
    frontmatter_node: FrontmatterNode = MissingFrontmatter()
    problems: tuple[SchemaProblems, ...] = ()
    fields: SkillFields = FrozenMapping({})
    owner: FrontmatterOwner | None = None
    anchor_set: frozenset[Anchor] = frozenset()
    base_name: str | None = None

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

    def anchors(self) -> frozenset[Anchor]:
        """The anchors this was built with."""
        return self.anchor_set

    def link_targets(self) -> Mapping[NormalisedLinkPath, LinkTargetEntry]:
        """The targets this was built with."""
        return self.target_map

    def link_base(self) -> LinkBase | None:
        """The base this was built with."""
        return self.base

    def document_name(self) -> str | None:
        """The name this was built with."""
        return self.name

    def document_base(self) -> str | None:
        """The base this was built with."""
        return self.base_name

    def line_count(self) -> LineCount:
        """The count this was built with."""
        return self.line_total

    def frontmatter(self) -> FrontmatterNode:
        """The block this was built with."""
        return self.frontmatter_node

    def schema_problems(self) -> tuple[SchemaProblems, ...]:
        """The problems this was built with."""
        return self.problems

    def skill_fields(self) -> SkillFields:
        """The fields this was built with."""
        return self.fields

    def frontmatter_owner(self) -> FrontmatterOwner:
        """The owner this was built with; a query that asks for one is run over primitives that hold it."""
        assert self.owner is not None, 'the primitives were built without an owner'
        return self.owner

    def query[T](self, query: Query[T]) -> T:
        """The answer of the query over these same primitives."""
        return query(self)
