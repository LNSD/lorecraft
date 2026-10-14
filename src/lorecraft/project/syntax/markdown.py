"""The Markdown parser, read into the values a document's parse tree is derived from.

The parser is wenmode, and this module is the only place it is used: its nodes are mutable and its API is pre-1.0,
so what leaves here is always this package's own frozen values, never a wenmode type. A wenmode upgrade changes
this module alone, and what `document` derives from these values does not move with it.

What is read here is what the parser decides: where the frontmatter block is, which text is a heading, a code block
or a link, where each sits, and the text a heading's inline nodes render as. What a section holds, how many prose
words it counts and how a repeated anchor is numbered are derived in `document`, from the values handed over here.

The frontmatter block is decoded by `parse_markdown_frontmatter` alone. The full parse finds the same block, so it is
not read as Markdown, but leaves it undecoded: a check that reads the frontmatter asks for it apart from the tree,
so decoding it in the full parse as well would decode every block twice.

The one place the parser does not decide is where that block is, for `parse_markdown_frontmatter`: it finds the block
with a scan of its own that mirrors wenmode's frontmatter plugin, held to it by `tests/it/test_frontmatter_scan.py`.
A wenmode upgrade that changes the plugin is caught there, not here.
"""

import re
from bisect import bisect_left
from dataclasses import dataclass
from typing import Final, assert_never

from wenmode import Wenmode
from wenmode.ast import plain_text
from wenmode.nodes import Code, Html, Image, Literal, Node, Parent, Position
from wenmode.nodes import Heading as WenmodeHeading
from wenmode.nodes import Link as WenmodeLink
from wenmode.plugins import frontmatter

from lorecraft.core.lines import newline_offsets
from lorecraft.core.num import NonZeroUnsignedInt

from .frontmatter import FrontmatterNode, MissingFrontmatter, decode_frontmatter
from .heading import HeadingLevel
from .link import Link
from .position import LineNumber

_FRONTMATTER_KEY: Final[str] = 'frontmatter'
"""Where wenmode's frontmatter plugin stores the decoded block on the root node's `data`."""


def _skip_frontmatter(block: str) -> None:
    """The full parser's frontmatter loader, which decodes nothing.

    The full parser loads the frontmatter plugin only so the block is not read as Markdown. The plugin always hands
    the block to a loader, and falls back to its own `key: value` splitter when given none, so this one is passed
    to leave the block undecoded: `parse_markdown_frontmatter` decodes it.

    Args:
        block: The lines between the delimiters, which are not read.
    """
    return None


_DELIMITER: Final[re.Pattern[str]] = re.compile(r'---[ \t]*(?:\r?\n)?')
"""A frontmatter delimiter line, as `str.splitlines` keeps it: `---`, trailing spaces and tabs, its line ending.

This is the line wenmode's frontmatter plugin accepts for both the opening and the closing delimiter, so a line
that is anything else, a leading space or a byte order mark included, is no delimiter.
"""

# The parser serves every call. A wenmode parser keeps nothing of a document between parses: each parse builds its
# own state, and the parser holds only its rules, which nothing changes after they are built here. So it can be
# shared, by several threads too, and its rules are not rebuilt for every document.
_FULL_PARSER: Final[Wenmode] = Wenmode(
    plugins=[frontmatter.configure(load=_skip_frontmatter, data_key=_FRONTMATTER_KEY)],
    positions=True,
)
"""The full Markdown parser: every CommonMark rule, a position on every node, the frontmatter block skipped."""


@dataclass(frozen=True, slots=True)
class HeadingBlock:
    """One of the document's own top-level blocks that is a heading.

    Attributes:
        level: The heading depth, 1 for a title through 6.
        text: The heading's plain text, inline markup stripped, inline HTML and an image's text kept.
        line: The document line the heading starts on.
    """

    level: HeadingLevel
    text: str
    line: LineNumber

    def __post_init__(self) -> None:
        """Fail on a level outside 1 to 6, which the type rules out but cannot stop at run time.

        The type is checked only before the code runs, so a value that reached `level` through `Any` or a `cast`
        is caught here instead.

        Raises:
            AssertionError: If `level` is not in 1..6.
        """
        match self.level:
            case 1 | 2 | 3 | 4 | 5 | 6:
                pass
            case _:
                assert_never(self.level)


@dataclass(frozen=True, slots=True)
class ContentBlock:
    """One of the document's own top-level blocks that is not a heading: a paragraph, a list, a code block, and so on.

    Attributes:
        source_outside_code: The block's source text, cut at every code block it holds, nested ones included, with
            the code blocks left out: the pieces before, between and after them, in document order. A block with
            no code block is one piece, and a block that is a code block is two empty ones.
    """

    source_outside_code: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MarkdownTree:
    """What the parser reads in one document, in this package's own values.

    Attributes:
        blocks: The document's own top-level blocks, in document order. A heading inside a blockquote or a list
            item is part of that block, not a block of its own.
        heading_texts: The text every heading anywhere in the document renders as, nested ones included, in
            document order: what GitHub derives a heading's anchor from. Unlike `HeadingBlock.text`, inline HTML
            and an image give no text here.
        links: Every link and image anywhere in the document, nested ones included, in document order.
    """

    blocks: tuple[HeadingBlock | ContentBlock, ...]
    heading_texts: tuple[str, ...]
    links: tuple[Link, ...]


def parse_markdown(text: str) -> MarkdownTree:
    """Parse one document's text with the full Markdown parser. Pure: raises nothing.

    The frontmatter block is found as `parse_markdown_frontmatter` finds it, but is neither decoded nor a block of
    the tree, and the lines after it keep their document lines.

    Args:
        text: The document's whole text, frontmatter block included; empty parses to a tree with no block.
    """
    root = _FULL_PARSER.parse(text)
    # Built once per document, so that a node's line is a binary search rather than a count from the start of the
    # text, which would make a parse cost every node times the document's size.
    newlines = newline_offsets(text)
    heading_texts: list[str] = []
    links: list[Link] = []
    _collect_headings_and_links(newlines, root, heading_texts, links)
    return MarkdownTree(
        blocks=tuple(_block(text, newlines, block) for block in root.children),
        heading_texts=tuple(heading_texts),
        links=tuple(links),
    )


def parse_markdown_frontmatter(text: str) -> FrontmatterNode:
    """Parse only the frontmatter block of one document's text. Pure: raises nothing.

    The block is a `---` line as the document's first line, closed by the next `---` line, each allowing trailing
    whitespace only. The lines between them go to `decode_frontmatter`, which never raises, so a broken block cannot
    fail the parse. A document with no such block, or one never closed, has `MissingFrontmatter`.

    `parse_markdown` finds the same block, with wenmode's frontmatter plugin. The plugin only ever claims the
    document's first line, where it is tried before every Markdown rule, so what it finds does not depend on the
    rules. The block is found here by a direct scan of the lines instead of a parse with no rules: that parser
    still reads the whole body as paragraphs, which is wasted work when only the block is wanted.

    Args:
        text: The document's whole text, frontmatter block included.
    """
    block = _find_frontmatter_block(text)
    if block is None:
        return MissingFrontmatter()
    return decode_frontmatter(block)


def _find_frontmatter_block(text: str) -> str | None:
    r"""The lines between the document's two `---` delimiters, line endings kept, or None when it has no block.

    The block is the one the full parser finds, so it ends lines where the parser does, which includes a form feed,
    a vertical tab, U+0085 and the Unicode line and paragraph separators. The block's text keeps its line endings,
    and the lines after it are numbered by the line breaks `lorecraft.core.lines` defines, as every finding
    numbers them.

    Args:
        text: The document's whole text.
    """
    # wenmode's parser splits lines with `str.splitlines`, so another split would find another block than the
    # full parse does.
    lines = text.splitlines(keepends=True)
    if not lines or _DELIMITER.fullmatch(lines[0]) is None:
        return None
    for index in range(1, len(lines)):
        if _DELIMITER.fullmatch(lines[index]) is not None:
            return ''.join(lines[1:index])
    return None


def _block(text: str, newlines: tuple[int, ...], node: Node) -> HeadingBlock | ContentBlock:
    r"""One of the root's own blocks, as a heading with its level, text and line, or as the source of any other.

    Args:
        text: The document's text, which the block's position indexes into.
        newlines: The offset where each line break in `text` starts, as `newline_offsets` returns them.
        node: One of the root's children, in the tree `parse_markdown` parsed.
    """
    if isinstance(node, WenmodeHeading):
        return HeadingBlock(
            level=_heading_level(node.depth),
            text=plain_text(node.children),
            line=_line(newlines, _position(node)),
        )
    return ContentBlock(source_outside_code=_source_outside_code(text, node))


def _heading_level(depth: int) -> HeadingLevel:
    """A wenmode heading's depth as a heading level, which wenmode types as any `int`.

    Args:
        depth: The `depth` of a wenmode heading.
    """
    match depth:
        case 1 | 2 | 3 | 4 | 5 | 6:
            return depth
        case _:
            # wenmode follows CommonMark, which gives every ATX and setext heading a depth of 1 to 6.
            raise AssertionError(f'unreachable: a Markdown heading is 1 to 6 deep, got {depth}')


def _source_outside_code(text: str, block: Node) -> tuple[str, ...]:
    """A block's source text, cut at every code block it holds and with those code blocks left out.

    A code block, fenced or indented, is cut out wherever it sits, a nested one such as inside a list item
    included. The rest is the source as written rather than its parsed inlines, so a link reads as the words its
    source is written with.

    Args:
        text: The document's text, which the block's position indexes into.
        block: One of the root's own blocks, in the tree `parse_markdown` parsed.
    """
    span = _position(block)
    pieces: list[str] = []
    start = span.start
    for code in _code_spans(block):
        pieces.append(text[start : code.start])
        start = code.end
    pieces.append(text[start : span.end])
    return tuple(pieces)


def _code_spans(node: Node) -> list[Position]:
    """Where each code block in the node sits, the node itself included, in document order.

    A code block holds text, never another block, so no span found here contains another.

    Args:
        node: Root of the subtree to search, in the tree `parse_markdown` parsed; a leaf is searched as itself.
    """
    if isinstance(node, Code):
        return [_position(node)]
    if not isinstance(node, Parent):
        return []
    spans: list[Position] = []
    for child in node.children:
        spans.extend(_code_spans(child))
    return spans


def _collect_headings_and_links(
    newlines: tuple[int, ...], node: Node, heading_texts: list[str], links: list[Link]
) -> None:
    r"""Append the rendered text of every heading, and every link and image, in the node and below it.

    The whole tree is walked, unlike for the blocks: a heading in a list item or a blockquote still renders with
    an anchor a link can name, and a link there is as much the document's as one in a top-level paragraph. Both
    lists grow in document order, and an image inside a link's text comes after that link.

    Args:
        newlines: The offset where each line break in the document's text starts, as `newline_offsets` returns them,
            which gives each link its line from its position.
        node: Root of the subtree to walk; a leaf is walked as itself.
        heading_texts: Where each heading's rendered text is appended.
        links: Where each link and image is appended.
    """
    if isinstance(node, WenmodeHeading):
        heading_texts.append(_rendered_text(node.children))
    if isinstance(node, WenmodeLink | Image):
        links.append(Link(url=node.url, line=_line(newlines, _position(node))))
    if isinstance(node, Parent):
        for child in node.children:
            _collect_headings_and_links(newlines, child, heading_texts, links)


def _rendered_text(nodes: list[Node]) -> str:
    """The text a heading's inline nodes render as, which is what GitHub derives the heading's anchor from.

    Text and inline code give their text, and emphasis, a link and any other container give their children's.
    Inline HTML gives nothing, since GitHub renders it as markup rather than text, and neither does an image: the
    rendered `<img>` holds no text. That is where this differs from wenmode's `plain_text`, which keeps both.

    Args:
        nodes: Inline children of a heading, in order; nested containers are read recursively.
    """
    parts: list[str] = []
    for node in nodes:
        if isinstance(node, Html | Image):
            continue
        if isinstance(node, Literal):
            parts.append(node.value)
        elif isinstance(node, Parent):
            parts.append(_rendered_text(node.children))
    return ''.join(parts)


def _line(newlines: tuple[int, ...], span: Position) -> LineNumber:
    r"""The document line a node's span starts on, a block's or an inline's alike.

    wenmode reports a node's position as a character offset into the text; every line before the offset ends in
    a line break, so the line is one more than the number of line breaks that start before the offset. A node never
    starts between the halves of a `\r\n` pair, so this agrees with `lorecraft.core.lines.line_at`.

    Args:
        newlines: The offset where each line break in the document's text starts, as `newline_offsets` returns them.
        span: Where the node to locate sits, as `_position` reads it.
    """
    return LineNumber(NonZeroUnsignedInt(bisect_left(newlines, span.start) + 1))


def _position(node: Node) -> Position:
    """Where a node sits in the document's text, as character offsets.

    Every node `parse_markdown` reads has a position, since its parser is built with `positions=True`. wenmode's
    types cannot say so: positions are a flag the parser takes at runtime, so every node declares its `position`
    optional. This is the one place the module turns that optional into a `Position`, so every other helper that
    needs a node's span reads it here.

    Args:
        node: Node of the tree `parse_markdown` parsed. A tree from any other parser, such as
            `parse_markdown_frontmatter`'s, may lack positions.
    """
    if node.position is None:
        raise AssertionError('unreachable: the full parser is built with positions=True')
    return node.position
