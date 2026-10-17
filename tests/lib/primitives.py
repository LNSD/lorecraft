"""Primitives held as given, for a caller that has no database."""

from collections.abc import Mapping
from dataclasses import dataclass

from lorecraft.core.mapping import FrozenMapping
from lorecraft.core.num import UnsignedInt
from lorecraft.project.link_target import DocumentLink, LinkBase, LinkTargetEntry
from lorecraft.project.query import Query
from lorecraft.project.schemas import FrontmatterOwner, SchemaProblems, SkillFields, StructureSpec
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
        document_link_list: The links to another document, with their corpus, filename and back link.
        corpus: The corpus the document lies in.
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
    document_link_list: tuple[DocumentLink, ...] = ()
    corpus: str | None = None

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

    def item_name(self) -> str | None:
        """The name this was built with."""
        return self.name

    def item_base(self) -> str | None:
        """The base this was built with."""
        return self.base_name

    def linked_documents(self) -> tuple[DocumentLink, ...]:
        """The links this was built with."""
        return self.document_link_list

    def item_corpus(self) -> str | None:
        """The corpus this was built with."""
        return self.corpus

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
