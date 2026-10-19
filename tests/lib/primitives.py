"""Primitives held as given, for a caller that has no database."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

from lorecraft.core.mapping import FrozenMapping
from lorecraft.core.num import UnsignedInt
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.corpus import CorpusName
from lorecraft.project.item import DocumentOrigin, ItemOrigin, MarkdownItemRef
from lorecraft.project.link_target import DocumentLink, LinkBase, LinkTargetEntry
from lorecraft.project.query import (
    DecodedText,
    Query,
    SchemaQuery,
    item_corpus,
    item_frontmatter,
    item_line_count,
    item_name,
    item_parse,
    item_structure_specs,
    item_token_count,
)
from lorecraft.project.schemas import SpecName, StructureSpec
from lorecraft.project.syntax import (
    Anchor,
    FrontmatterNode,
    Heading,
    LineCount,
    Link,
    MissingFrontmatter,
    NormalisedLinkPath,
    ParsedDocument,
    TokenCount,
)
from lorecraft.project.workspace import Governance
from lorecraft.rules.link.queries import linked_documents
from lorecraft.schemas import SchemaInput, SchemaReference
from lorecraft.schemas.builtin import AGENT_SKILLS_SCHEMA_INPUT, AGENT_SKILLS_SCHEMA_REFERENCE


class _BundledAgentSkillsSchemaPrimitives:
    """Schema primitives for standalone rule tests; only the bundled skills subject is available."""

    def schema_input(self) -> SchemaInput:
        """The immutable bundled Agent Skills schema input."""
        return AGENT_SKILLS_SCHEMA_INPUT

    def query_schema[T](self, ref: SchemaReference, query: SchemaQuery[T]) -> T:
        """Standalone rule tests do not expose nested schema subjects."""
        raise NotImplementedError(f'standalone primitives cannot read nested schema {ref}')


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
    name: AspectFilename | SpecName | None = None
    line_total: LineCount = LineCount(UnsignedInt(0))
    frontmatter_node: FrontmatterNode = MissingFrontmatter()
    anchor_set: frozenset[Anchor] = frozenset()
    base_name: AspectFilename | SpecName | None = None
    document_link_list: tuple[DocumentLink, ...] = ()
    corpus: CorpusName | None = None
    origin_value: ItemOrigin = DocumentOrigin(expected_name='setup', corpus='guide', schema_paths=())
    governance_value: Governance | None = None
    builtin_schema: bool = True

    def item_origin(self) -> ItemOrigin:
        """The origin this was built with."""
        return self.origin_value

    def item_text(self) -> DecodedText | None:
        """Standalone test facts have no decoded witness; derived answers are supplied below."""
        return None

    def item_governance(self) -> Governance | None:
        """The governance this was built with."""
        return self.governance_value

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

    def item_name(self) -> AspectFilename | SpecName | None:
        """The name this was built with."""
        return self.name

    def item_base(self) -> AspectFilename | SpecName | None:
        """The base this was built with."""
        return self.base_name

    def item_corpus(self) -> CorpusName | None:
        """The corpus this was built with."""
        return self.corpus

    def line_count(self) -> LineCount:
        """The count this was built with."""
        return self.line_total

    def frontmatter(self) -> FrontmatterNode:
        """The block this was built with."""
        return self.frontmatter_node

    def query[T](self, query: Query[T]) -> T:
        """The answer of the query over these same primitives."""
        if query is linked_documents:
            return cast('T', self.document_link_list)
        answers: dict[object, object] = {
            item_frontmatter: self.frontmatter_node,
            item_line_count: self.line_total,
            item_name: self.name,
            item_corpus: self.corpus,
            item_parse: ParsedDocument(self.heading_list, self.anchor_set, self.link_list),
            item_structure_specs: self.specs,
            item_token_count: self.token_total,
        }
        if query in answers:
            return cast('T', answers[query])
        return query(self)

    def query_at[T](self, ref: MarkdownItemRef, query: Query[T]) -> T:
        """No other item is available to this standalone primitive value."""
        raise NotImplementedError('standalone primitives cannot read another item')

    def query_schema[T](self, ref: SchemaReference, query: SchemaQuery[T]) -> T:
        """Answer only the bundled skills subject for standalone skill rule tests."""
        if ref != AGENT_SKILLS_SCHEMA_REFERENCE:
            raise NotImplementedError(f'standalone primitives cannot read schema {ref}')
        return query(_BundledAgentSkillsSchemaPrimitives())
