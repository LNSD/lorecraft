"""Facts derived from one item's decoded text or governance."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lorecraft.core.num import UnsignedInt
from lorecraft.project.aspect import AspectFilename, AspectName
from lorecraft.project.corpus import CorpusName
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
    from lorecraft.core.path import RootRelativePath
    from lorecraft.project.query import GovernancePrimitives, ItemPrimitives, NameHierarchyPrimitives
    from lorecraft.project.schemas.name import SpecName
    from lorecraft.project.schemas.structure import BuiltinLineBudget, StructureSpec
    from lorecraft.schemas import BuiltinOrigin


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


def item_structure_sources(
    primitives: GovernancePrimitives,
) -> tuple[tuple[RootRelativePath | BuiltinOrigin, BuiltinLineBudget | StructureSpec], ...]:
    """The builtin and repository structure specs governing this item, with each source."""
    return primitives.structure_sources()


def item_name(primitives: NameHierarchyPrimitives) -> AspectFilename | AspectName | SpecName | None:
    """The typed name declared by this item's descriptor when its text decodes."""
    if primitives.text() is None:
        return None
    return primitives.descriptor().name


def item_corpus(primitives: NameHierarchyPrimitives) -> CorpusName | None:
    """The typed corpus declared by this item's descriptor when its text decodes."""
    if primitives.text() is None:
        return None
    return primitives.descriptor().corpus


def item_base(primitives: NameHierarchyPrimitives) -> AspectFilename | SpecName | None:
    """The nearest existing document or specification name this item extends.

    The base is looked for among the item's corpus names; `None` when it has no name or is not UTF-8.
    """
    if primitives.text() is None:
        return None
    hierarchy = primitives.name_hierarchy()
    return hierarchy.base_name
