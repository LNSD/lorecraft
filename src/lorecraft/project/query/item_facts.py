"""Facts derived from one item's decoded text or governance."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lorecraft.core.num import UnsignedInt
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.corpus import CorpusName
from lorecraft.project.item import DocumentOrigin, SpecificationOrigin
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
    from lorecraft.project.query import Primitives
    from lorecraft.project.schemas.name import SpecName
    from lorecraft.project.schemas.structure import StructureSpec


def item_frontmatter(primitives: Primitives) -> FrontmatterNode:
    """The item's frontmatter, parsed from its decoded text alone."""
    source = primitives.item_text()
    return parse_frontmatter(source.text) if source is not None else MissingFrontmatter()


def item_parse(primitives: Primitives) -> ParsedDocument:
    """The item's parse tree, built from its decoded text alone."""
    source = primitives.item_text()
    return parse_document(source.text) if source is not None else parse_document('')


def item_token_count(primitives: Primitives) -> TokenCount:
    """The tokens in the item's whole decoded file; zero when it is not UTF-8."""
    source = primitives.item_text()
    return count_tokens(source.text) if source is not None else TokenCount(UnsignedInt(0))


def item_line_count(primitives: Primitives) -> LineCount:
    """The lines in the item's whole decoded file; zero when it is not UTF-8."""
    source = primitives.item_text()
    return count_lines(source.text) if source is not None else LineCount(UnsignedInt(0))


def item_structure_specs(primitives: Primitives) -> tuple[StructureSpec, ...]:
    """The structure specifications of the item's governance, if any."""
    governance = primitives.item_governance()
    return governance.structure_specs() if governance is not None else ()


def item_name(primitives: Primitives) -> AspectFilename | SpecName | None:
    """The typed name declared by this item's origin, when it has readable text."""
    source = primitives.item_text()
    if source is None:
        return None
    origin = source.descriptor.origin
    if isinstance(origin, DocumentOrigin):
        return AspectFilename.parse(origin.expected_name)
    if isinstance(origin, SpecificationOrigin):
        from lorecraft.project.schemas.name import parse_spec_name

        return parse_spec_name(origin.expected_name)
    return None


def item_corpus(primitives: Primitives) -> CorpusName | None:
    """The typed corpus declared by a readable document item."""
    source = primitives.item_text()
    origin = source.descriptor.origin if source is not None else None
    return CorpusName.parse(origin.corpus) if isinstance(origin, DocumentOrigin) else None
