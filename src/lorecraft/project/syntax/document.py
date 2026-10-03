"""The root of a document's parse tree: what every check reads instead of the document's text.

A parse tree is a pure function of the text, so a document is parsed once and every check shares the result.
The Markdown itself is read by `markdown`, which hands this module the package's own frozen values; what is
derived from them here is Lorecraft's. The tree keeps the frontmatter, the document's top-level headings, how many
prose words each heading's section holds, the anchor of every heading at any depth, and every link's destination
and line. The rest of the content is not kept: no check reads it yet.

A heading's anchor is the name a fragment-only link such as `#usage` points at. `Anchor` derives it from the
heading's text as GitHub does; what is read here is which headings take one, the text GitHub renders each from,
and how a repeat is numbered.

A prose word is whitespace-delimited text outside code blocks, table rows and headings: a section's words say how
concise its prose is, and code and tables are free because they are the examples and references a document exists
to hold. What the whole file costs an agent that loads it is a different question, answered from the raw text by
`count_tokens` without a parse.

A check that reads nothing but the frontmatter does not need the tree: `parse_frontmatter` finds and decodes
the same block for a fraction of the cost, so it is the cheap path, and `parse_document` the full one.
"""

from dataclasses import dataclass
from typing import assert_never

from .anchor import Anchor
from .frontmatter import FrontmatterNode
from .heading import Heading, HeadingLevel
from .link import Link
from .markdown import ContentBlock, HeadingBlock, parse_markdown, parse_markdown_frontmatter


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    """One document's parse tree.

    Not hashable when its frontmatter holds a mapping, since `Frontmatter` holds a dict.

    Attributes:
        frontmatter: The frontmatter block, or the reason there is no usable one.
        headings: The document's own top-level headings, in document order.
        anchors: The anchor of every heading anywhere in the document, nested ones included, as GitHub derives
            it; a repeated heading's numbered anchors are all here.
        links: Every link and image anywhere in the document, nested ones included, in document order.
    """

    frontmatter: FrontmatterNode
    headings: tuple[Heading, ...]
    anchors: frozenset[Anchor]
    links: tuple[Link, ...]


def parse_document(text: str) -> ParsedDocument:
    """Parse one document's text into its parse tree. Pure: raises nothing.

    The frontmatter block is found and decoded as `parse_markdown` describes; a document with no such block has
    `MissingFrontmatter`.

    Args:
        text: The document's whole text, frontmatter block included; empty parses to a document with none.
    """
    tree = parse_markdown(text)
    block_words = [_prose_words(block) for block in tree.blocks]
    return ParsedDocument(
        frontmatter=tree.frontmatter,
        headings=_headings(tree.blocks, block_words),
        anchors=_anchors(tree.heading_texts),
        links=tree.links,
    )


def parse_frontmatter(text: str) -> FrontmatterNode:
    """Parse only the frontmatter block of one document's text. Pure: raises nothing.

    Equal to `parse_document(text).frontmatter` for every text. The block is found as `parse_document` finds it,
    but the rest of the text is not read as Markdown, which costs a small fraction of the full parse.

    Args:
        text: The document's whole text, frontmatter block included.
    """
    return parse_markdown_frontmatter(text)


def _headings(blocks: tuple[HeadingBlock | ContentBlock, ...], block_words: list[int]) -> tuple[Heading, ...]:
    """The headings among the root's own blocks, each with its line, its section's words and whether it is empty.

    Only the root's own blocks are read, never the whole tree: a heading inside a blockquote or a list item is part
    of that block, so it is left out without being looked for.

    Args:
        blocks: The root's own blocks, in document order.
        block_words: The prose words of each block, at the same index as the block.
    """
    headings: list[Heading] = []
    for index, block in enumerate(blocks):
        match block:
            case HeadingBlock():
                following = blocks[index + 1] if index + 1 < len(blocks) else None
                # A section is empty when the next block closes it: the end of the document, or a heading of the
                # same or a higher level. A deeper heading opens a subsection, whose content is this section's own.
                empty = following is None or _closes_section(following, block.level)
                headings.append(
                    Heading(
                        level=block.level,
                        text=block.text,
                        line=block.line,
                        empty=empty,
                        words=_section_words(blocks, block_words, index, block.level),
                    )
                )
            case ContentBlock():
                # Content belongs to the section a heading before it opened; it opens none of its own.
                continue
            case _:
                assert_never(block)
    return tuple(headings)


def _anchors(heading_texts: tuple[str, ...]) -> frozenset[Anchor]:
    """The anchor GitHub gives each heading in the document, a repeated one numbered as GitHub numbers it.

    Every heading takes one, unlike for `_headings`: a heading in a list item or a blockquote still renders with
    an anchor a link can name. Headings take their anchors in document order. The first heading to take an anchor
    keeps it bare; the next one with the same anchor gets `-1` added, the one after that `-2`, and so on. A
    numbered anchor another heading already holds is skipped, so `Foo 1`, `Foo`, `Foo` give `foo-1`,
    `foo` and `foo-2`: no two headings share an anchor.

    Args:
        heading_texts: The rendered text of every heading anywhere in the document, in document order.
    """
    # Every anchor taken so far, each mapped to how many times it has been numbered as a bare anchor.
    occurrences: dict[Anchor, int] = {}
    for heading_text in heading_texts:
        bare = Anchor.from_heading(heading_text)
        anchor = bare
        while anchor in occurrences:
            occurrences[bare] += 1
            anchor = bare.numbered(occurrences[bare])
        occurrences[anchor] = 0
    return frozenset(occurrences)


def _section_words(
    blocks: tuple[HeadingBlock | ContentBlock, ...], block_words: list[int], heading_index: int, level: HeadingLevel
) -> int:
    """The prose words in the section a heading opens, its subsections' included.

    The section runs to the next heading of the same or a higher level, or to the end of the document. A deeper
    heading does not close it, and holds no prose words of its own, so adding every block's words is enough.

    Args:
        blocks: The root's own blocks, in document order.
        block_words: The prose words of each block, at the same index as the block.
        heading_index: Where the heading opening the section sits in `blocks`.
        level: That heading's depth.
    """
    words = 0
    for index in range(heading_index + 1, len(blocks)):
        if _closes_section(blocks[index], level):
            break
        words += block_words[index]
    return words


def _closes_section(block: HeadingBlock | ContentBlock, level: HeadingLevel) -> bool:
    """Whether a block ends the section a heading of the given level opens.

    A heading of the same or a higher level ends it. A deeper heading opens a subsection, which is the section's
    own content, and so is every other block.

    Args:
        block: The block after the heading, or after the section's content so far.
        level: The depth of the heading that opened the section.
    """
    match block:
        case HeadingBlock():
            return block.level <= level
        case ContentBlock():
            return False
        case _:
            assert_never(block)


def _prose_words(block: HeadingBlock | ContentBlock) -> int:
    """The prose words one of the root's blocks holds: whitespace-delimited tokens of its source text.

    A heading and a code block, fenced or indented, hold none, and neither does a code block nested in the block,
    such as one inside a list item. The rest is counted from its source text rather than from its parsed inlines,
    so a link counts as the words its source is written with.

    Args:
        block: One of the root's own blocks.
    """
    match block:
        case HeadingBlock():
            return 0
        case ContentBlock():
            words = 0
            for source in block.source_outside_code:
                words += _source_words(source)
            return words
        case _:
            assert_never(block)


def _source_words(source: str) -> int:
    """The whitespace-delimited tokens of a stretch of Markdown source, table rows left out.

    Args:
        source: Markdown source with no code block in it; a line starting with `|` is skipped as a table row.
    """
    words = 0
    for line in source.splitlines():
        # The parser has no table extension, so a table is read as a paragraph of `|` lines. Those lines are
        # skipped here: a table is a reference, not prose.
        if line.strip().startswith('|'):
            continue
        words += len(line.split())
    return words
