"""Facts derived from one item's decoded text or governance."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lorecraft.core.num import UnsignedInt
from lorecraft.project.aspect import AspectFilename, AspectName
from lorecraft.project.corpus import CorpusName
from lorecraft.project.item import ItemType
from lorecraft.project.syntax import (
    FrontmatterNode,
    LineCount,
    MissingFrontmatter,
    ParsedDocument,
    TokenCount,
    count_lines,
    count_tokens,
    parse_document,
    parse_frontmatter,
)

if TYPE_CHECKING:
    from lorecraft.project.query import ItemPrimitives, NameHierarchyPrimitives
    from lorecraft.project.schemas.name import SpecName
    from lorecraft.project.schemas.structure import StructureSpec


def item_frontmatter(primitives: ItemPrimitives) -> FrontmatterNode:
    """The item's frontmatter, parsed from its decoded text alone."""
    source = primitives.text()
    return parse_frontmatter(source.text) if source is not None else MissingFrontmatter()


def item_parse(primitives: ItemPrimitives) -> ParsedDocument:
    """The item's parse tree, built from its decoded text alone."""
    source = primitives.text()
    return parse_document(source.text) if source is not None else parse_document('')


def item_token_count(primitives: ItemPrimitives) -> TokenCount:
    """The tokens in the item's whole decoded file; zero when it is not UTF-8."""
    source = primitives.text()
    return count_tokens(source.text) if source is not None else TokenCount(UnsignedInt(0))


def item_line_count(primitives: ItemPrimitives) -> LineCount:
    """The lines in the item's whole decoded file; zero when it is not UTF-8."""
    source = primitives.text()
    return count_lines(source.text) if source is not None else LineCount(UnsignedInt(0))


def item_structure_specs(primitives: ItemPrimitives) -> tuple[StructureSpec, ...]:
    """The structure specifications of the item's governance, if any."""
    governance = primitives.governance()
    return governance.structure_specs() if governance is not None else ()


def item_name(primitives: NameHierarchyPrimitives) -> AspectFilename | AspectName | SpecName | None:
    """The typed name declared by this item's descriptor when its text decodes."""
    if primitives.text() is None:
        return None
    return primitives.item_descriptor().name


def item_corpus(primitives: NameHierarchyPrimitives) -> CorpusName | None:
    """The typed corpus declared by this item's descriptor when its text decodes."""
    if primitives.text() is None:
        return None
    return primitives.item_descriptor().corpus


def item_base(primitives: NameHierarchyPrimitives) -> AspectFilename | SpecName | None:
    """The nearest existing document or specification name this item extends.

    A document's base is looked for among its corpus's documents, a meta spec's among the specifications; `None` for
    any other item or one that is not UTF-8.
    """
    if primitives.text() is None:
        return None
    descriptor = primitives.item_descriptor()
    model = primitives.model()
    if isinstance(descriptor.name, AspectFilename):
        if descriptor.corpus is None:
            return None
        corpus = model.find_corpus(descriptor.corpus)
        if corpus is None:
            return None
        base = corpus.document_base(descriptor.name)
        return None if base is None else base.filename
    if descriptor.type is ItemType.META_SPEC:
        # These imports stay local to avoid a cycle through the document query modules.
        from lorecraft.project.document import MetaSpecRef
        from lorecraft.project.schemas.name import parse_spec_name

        base_spec = model.find_specification_base(MetaSpecRef(descriptor.ref.path))
        return None if base_spec is None else parse_spec_name(base_spec.name)
    return None
