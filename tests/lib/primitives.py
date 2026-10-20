"""Primitives held as given, for a caller that has no database."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import cast

from lorecraft.core.mapping import FrozenMapping
from lorecraft.core.num import UnsignedInt
from lorecraft.core.path import RootRelativePath
from lorecraft.project.aspect import AspectFilename, AspectName
from lorecraft.project.corpus import CorpusName
from lorecraft.project.document import DocumentRef, MetaSpecRef
from lorecraft.project.item import (
    DocumentOrigin,
    ItemDescriptor,
    ItemOrigin,
    ItemRef,
    SkillEntrypointOrigin,
)
from lorecraft.project.link_target import DocumentDirectory, DocumentLink, LinkBase, LinkTargetEntry
from lorecraft.project.query import (
    DecodedText,
    ItemQuery,
    QueryTargetRef,
    item_base,
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
from lorecraft.schemas import RepositoryOrigin, SchemaInput, SchemaRef
from lorecraft.schemas.builtin import AGENT_SKILLS_SCHEMA_INPUT, AGENT_SKILLS_SCHEMA_REFERENCE


class _BundledAgentSkillsSchemaPrimitives:
    """Schema primitives for standalone rule tests; only the bundled skills subject is available."""

    def schema_input(self) -> SchemaInput:
        """The immutable bundled Agent Skills schema input."""
        return AGENT_SKILLS_SCHEMA_INPUT

    def query_at[T](self, ref: QueryTargetRef, query: Callable[..., T]) -> T:
        """Standalone rule tests do not expose nested subjects."""
        raise NotImplementedError(f'standalone primitives cannot read another subject {ref}')


@dataclass(frozen=True, slots=True)
class _SchemaInputPrimitives:
    """The immutable registry input for a standalone schema query."""

    input: SchemaInput

    def schema_input(self) -> SchemaInput:
        """Return the input this fake schema subject represents."""
        return self.input

    def query_at[T](self, ref: QueryTargetRef, query: Callable[..., T]) -> T:
        """Standalone schema queries do not compose across subjects."""
        raise NotImplementedError(f'standalone schema primitives cannot read another subject {ref}')


@dataclass(frozen=True, slots=True)
class StructurePrimitives:
    """Primitives that hold the structure specifications as given, for a caller that has no database.

    Attributes:
        specs: The structure specifications that govern the item, in the order they apply.
        heading_list: The headings of the item's parse, in document order.
        token_total: The tokens in the item's whole file.
        link_list: The links of the item's parse, in document order.
        target_map: What the snapshot holds at the target of each relative link.
        link_base_value: Where the item's relative links are read from.
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
    link_base_value: LinkBase | None = None
    name: AspectFilename | SpecName | None = None
    line_total: LineCount = LineCount(UnsignedInt(0))
    frontmatter_node: FrontmatterNode = MissingFrontmatter()
    anchor_set: frozenset[Anchor] = frozenset()
    base_name: AspectFilename | SpecName | None = None
    document_link_list: tuple[DocumentLink, ...] = ()
    corpus: CorpusName | None = None
    origin_value: ItemOrigin = DocumentOrigin()
    governance_value: Governance | None = None
    builtin_schema: bool = True
    schema_inputs_value: Mapping[SchemaRef, SchemaInput] | None = None

    def origin(self) -> ItemOrigin:
        """The origin this was built with."""
        return self.origin_value

    def descriptor(self) -> ItemDescriptor:
        """The descriptor synthesized from this standalone test value."""
        name = self.name
        corpus = self.corpus
        path = RootRelativePath.parse(f'docs/{corpus or "guide"}/{name or "setup"}.md')
        link_base = self.link_base_value or DocumentDirectory(path.parent)
        schema_refs = (
            (AGENT_SKILLS_SCHEMA_REFERENCE,)
            if isinstance(self.origin_value, SkillEntrypointOrigin) and self.builtin_schema
            else ()
        ) + (self.governance_value.applicable_frontmatter_schema_refs() if self.governance_value is not None else ())
        return ItemDescriptor(
            ItemRef(path),
            path,
            link_base,
            self.origin_value,
            name,
            str(name or self.base_name or ''),
            corpus,
            schema_refs,
            frozenset(),
        )

    def model(self) -> StructurePrimitives:
        """The minimal name hierarchy available to standalone rule tests."""
        return self

    def find_corpus(self, name: CorpusName) -> StructurePrimitives | None:
        """Return this item's hierarchy only for the corpus the test supplied."""
        return self if self.corpus == name else None

    def find_specification_base(self, ref: MetaSpecRef) -> MetaSpecRef | None:
        """Standalone rule fixtures do not model specification hierarchies."""
        return None

    def name_base(
        self, corpus: CorpusName | None, name: AspectFilename | AspectName | SpecName | None
    ) -> AspectFilename | SpecName | None:
        """Return the supplied document base for the fixture's corpus and typed name."""
        if corpus != self.corpus or not isinstance(name, AspectFilename):
            return None
        base = self.document_base(name)
        return None if base is None else base.filename

    def document_base(self, filename: AspectFilename) -> DocumentRef | None:
        """Return the base explicitly supplied by a standalone document fixture."""
        if self.base_name is None:
            return None
        return DocumentRef(self.corpus or CorpusName.parse('guide'), self.base_name)

    def listed_name(self) -> str:
        """The original name this was built with."""
        return str(self.name or self.base_name or '')

    def text(self) -> DecodedText | None:
        """Standalone test facts have no decoded witness; derived answers are supplied below."""
        return None

    def governance(self) -> Governance | None:
        """The governance this was built with."""
        return self.governance_value

    def schema_inputs(self) -> Mapping[SchemaRef, SchemaInput]:
        """The immutable schema inputs available to standalone rule queries."""
        if self.schema_inputs_value is not None:
            return self.schema_inputs_value
        inputs: dict[SchemaRef, SchemaInput] = {}
        if self.builtin_schema:
            inputs[AGENT_SKILLS_SCHEMA_REFERENCE] = AGENT_SKILLS_SCHEMA_INPUT
        if self.governance_value is not None:
            for reference, schema in zip(
                self.governance_value.applicable_frontmatter_schema_refs(),
                self.governance_value.frontmatter_schemas(),
                strict=True,
            ):
                inputs[reference] = SchemaInput(reference, RepositoryOrigin(schema.spec, 'test'), schema.schema.schema)
        return FrozenMapping(inputs)

    def schema_input(self, reference: SchemaRef) -> SchemaInput | None:
        """Resolve one standalone schema reference from the fake registry."""
        return self.schema_inputs().get(reference)

    def query_at[T](self, ref: QueryTargetRef, query: Callable[..., T]) -> T:
        """Resolve a standalone schema subject from this fixture's schema inputs."""
        if ref == AGENT_SKILLS_SCHEMA_REFERENCE:
            return query(_BundledAgentSkillsSchemaPrimitives())
        if isinstance(ref, SchemaRef):
            schema_input = self.schema_inputs().get(ref)
            if schema_input is not None:
                return query(_SchemaInputPrimitives(schema_input))
        raise NotImplementedError(f'standalone primitives cannot read another subject {ref}')

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
        return self.link_base_value

    def item_name(self) -> AspectFilename | SpecName | None:
        """The name this was built with."""
        return self.name

    def base(self) -> AspectFilename | SpecName | None:
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

    def query[T](self, query: ItemQuery[T]) -> T:
        """The answer of the query over these same primitives."""
        if query is linked_documents:
            return cast('T', self.document_link_list)
        if query is item_frontmatter:
            return self.frontmatter_node
        if query is item_line_count:
            return self.line_total
        if query is item_parse:
            return ParsedDocument(self.heading_list, self.anchor_set, self.link_list)
        if query is item_structure_specs:
            return self.specs
        if query is item_corpus:
            return self.corpus
        if query is item_name:
            return self.name
        if query is item_base:
            return self.base_name
        if query is item_token_count:
            return self.token_total
        return query(self)
