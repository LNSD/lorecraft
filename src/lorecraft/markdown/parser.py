"""The Markdown parser, read into the values a document's parse tree is derived from.

The parser is wenmode, and this package is the only place it is used: its nodes are mutable and its API is pre-1.0,
so what leaves here is always this package's own frozen values, never a wenmode type. A wenmode upgrade changes
this package alone, and what `lorecraft.project.syntax.document` derives from these values does not move with it.

What is read here is what the parser decides: where the frontmatter block is, which text is a heading, a code block
or a link, where each sits, and the text a heading's inline nodes render as. What a section holds, how many prose
words it counts and how a repeated anchor is numbered are derived in `lorecraft.project.syntax.document`, from the
values handed over here.

The frontmatter block is found by `parse_markdown_frontmatter` as raw text and decoded by its caller in
`lorecraft.project`. The full parse finds the same block, so it is not read as Markdown.

The one place the parser does not decide is where that block is, for `parse_markdown_frontmatter`: it finds the block
with a scan of its own that mirrors wenmode's frontmatter plugin, held to it by `tests/it/test_frontmatter_scan.py`.
A wenmode upgrade that changes the plugin is caught there, not here.
"""

import re
from bisect import bisect_left
from dataclasses import dataclass
from typing import Final, Literal

from wenmode import Wenmode
from wenmode.nodes import Code, Html, Image, Node, Parent, Position
from wenmode.nodes import Heading as WenmodeHeading
from wenmode.nodes import Link as WenmodeLink
from wenmode.nodes import Literal as LiteralNode
from wenmode.plugins import frontmatter

from lorecraft.core.error import Unreachable
from lorecraft.core.lines import Line, TextOffset, newline_offsets
from lorecraft.core.num import NonZeroUnsignedInt, UnsignedInt

MarkdownLine = Line
"""A one-based document line, counted by the line breaks `lorecraft.core.lines` defines."""

type HeadingLevel = Literal[1, 2, 3, 4, 5, 6]
"""A heading's depth: 1 for a title through 6, the deepest Markdown has."""


@dataclass(frozen=True, slots=True)
class MarkdownLink:
    """A Markdown destination and its one-based line, before any path resolution.

    The URL is CommonMark-normalised: escapes and character references are decoded, then the value is
    percent-encoded. For example, `[x](</a b>)` yields `/a%20b`.
    """

    url: str
    line: MarkdownLine


_FRONTMATTER_KEY: Final[str] = 'frontmatter'
"""Where wenmode's frontmatter plugin stores the decoded block on the root node's `data`."""


def _skip_frontmatter(block: str) -> None:
    """The full parser's frontmatter loader, which decodes nothing.

    The full parser loads the frontmatter plugin only so the block is not read as Markdown. The plugin always hands
    the block to a loader, and falls back to its own `key: value` splitter when given none, so this one is passed
    to leave the block undecoded: `lorecraft.project.syntax.document.parse_frontmatter` decodes it.

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
class MarkdownHeading:
    """A heading anywhere in the document, with both texts it is read as.

    Attributes:
        level: The heading depth, 1 for a title through 6.
        text: The heading's plain text, inline markup stripped, inline HTML and an image's text kept.
        rendered_text: The text the heading renders as, which GitHub derives its anchor from: inline HTML and an
            image give no text here, unlike in `text`.
        line: The document line the heading starts on.
        top_level: Whether the heading is one of the document's own top-level blocks, rather than inside a
            blockquote or a list item.
    """

    level: HeadingLevel
    text: str
    rendered_text: str
    line: MarkdownLine
    top_level: bool


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
        headings: Every heading anywhere in the document, nested ones included, in document order. The top-level
            ones are the same values as the heading blocks.
        links: Every link and image anywhere in the document, nested ones included, in document order.
    """

    blocks: tuple[MarkdownHeading | ContentBlock, ...]
    headings: tuple[MarkdownHeading, ...]
    links: tuple[MarkdownLink, ...]


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
    top_level = {id(block) for block in root.children}
    headings: dict[int, MarkdownHeading] = {}
    links: list[MarkdownLink] = []
    _collect_headings_and_links(newlines, top_level, root, headings, links)
    return MarkdownTree(
        blocks=tuple(headings.get(id(block)) or _content(text, block) for block in root.children),
        headings=tuple(headings.values()),
        links=tuple(links),
    )


def parse_markdown_frontmatter(text: str) -> str | None:
    """Find the raw frontmatter block in one document's text, or return None. Pure: raises nothing.

    The block is a `---` line as the document's first line, closed by the next `---` line, each allowing trailing
    whitespace only. The lines between them are returned as raw text, line endings kept; the caller in
    `lorecraft.project` decodes them. A document with no such block, or one never closed, gives None.

    `parse_markdown` finds the same block, with wenmode's frontmatter plugin. The plugin only ever claims the
    document's first line, where it is tried before every Markdown rule, so what it finds does not depend on the
    rules. The block is found here by a direct scan of the lines instead of a parse with no rules: that parser
    still reads the whole body as paragraphs, which is wasted work when only the block is wanted.

    Args:
        text: The document's whole text, frontmatter block included.
    """
    return _find_frontmatter_block(text)


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


def _content(text: str, node: Node) -> ContentBlock:
    """One of the root's own blocks that is not a heading, as its source outside any code block.

    Args:
        text: The document's text, which the block's position indexes into.
        node: One of the root's children, in the tree `parse_markdown` parsed.
    """
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
            # SAFETY: wenmode follows CommonMark, which gives every ATX and setext heading a depth of 1 to 6
            raise Unreachable(f'a Markdown heading is 1 to 6 deep, got {depth}')


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
    newlines: tuple[TextOffset, ...],
    top_level: set[int],
    node: Node,
    headings: dict[int, MarkdownHeading],
    links: list[MarkdownLink],
) -> None:
    r"""Add every heading, and append every link and image, in the node and below it, in one walk.

    The whole tree is walked: a heading in a list item or a blockquote still renders with an anchor a link can
    name, and a link there is as much the document's as one in a top-level paragraph. Both collections grow in
    document order, and an image inside a link's text comes after that link.

    Args:
        newlines: The offset where each line break in the document's text starts, as `newline_offsets` returns them,
            which gives each heading and link its line from its position.
        top_level: The identity of each of the root's own children, which marks a heading as top-level.
        node: Root of the subtree to walk; a leaf is walked as itself.
        headings: Where each heading is added, keyed by its node's identity so the blocks reuse the same values.
        links: Where each link and image is appended.
    """
    if isinstance(node, WenmodeHeading):
        headings[id(node)] = MarkdownHeading(
            level=_heading_level(node.depth),
            text=_plain_text(node.children),
            rendered_text=_rendered_text(node.children),
            line=_line(newlines, _position(node)),
            top_level=id(node) in top_level,
        )
    if isinstance(node, WenmodeLink | Image):
        links.append(MarkdownLink(url=node.url, line=_line(newlines, _position(node))))
    if isinstance(node, Parent):
        for child in node.children:
            _collect_headings_and_links(newlines, top_level, child, headings, links)


def _rendered_text(nodes: list[Node]) -> str:
    """The text a heading's inline nodes render as, which is what GitHub derives the heading's anchor from.

    Text and inline code give their text, and emphasis, a link and any other container give their children's.
    Inline HTML gives nothing, since GitHub renders it as markup rather than text, and neither does an image: the
    rendered `<img>` holds no text. Unlike `_plain_text` (the text kept in `MarkdownHeading.text`), anchor text drops
    inline HTML and images.

    Args:
        nodes: Inline children of a heading, in order; nested containers are read recursively.
    """
    parts: list[str] = []
    for node in nodes:
        if isinstance(node, Html | Image):
            continue
        if isinstance(node, LiteralNode):
            parts.append(node.value)
        elif isinstance(node, Parent):
            parts.append(_rendered_text(node.children))
    return ''.join(parts)


def _plain_text(nodes: list[Node]) -> str:
    """The heading's plain text: inline markup stripped, HTML and image alt text kept, with block separators.

    Inline HTML is kept verbatim and adds no separator, so `Use <code>x</code> now` stays on one line.

    This mirrors wenmode 0.15's `plain_text` behavior, except that inline HTML adds no separator.
    """
    parts: list[str] = []
    previous_separated = False
    for node in nodes:
        text = _plain_text_node(node)
        if not text:
            continue
        separated = node.block and not isinstance(node, Html)
        if parts and (previous_separated or separated):
            parts.append('\n')
        parts.append(text)
        previous_separated = separated
    return ''.join(parts)


def _plain_text_node(node: Node) -> str:
    """A node's contribution to the plain text kept in `MarkdownHeading.text`."""
    if isinstance(node, Image):
        return node.alt
    if isinstance(node, LiteralNode):
        return node.value
    if isinstance(node, Parent):
        return _plain_text(node.children)
    label = getattr(node, 'label', None)
    if isinstance(label, str):
        return label
    identifier = getattr(node, 'identifier', None)
    return identifier if isinstance(identifier, str) else ''


def _line(newlines: tuple[TextOffset, ...], span: Position) -> MarkdownLine:
    r"""The document line a node's span starts on, a block's or an inline's alike.

    wenmode reports a node's position as a character offset into the text; every line before the offset ends in
    a line break, so the line is one more than the number of line breaks that start before the offset. A node never
    starts between the halves of a `\r\n` pair, so this agrees with `lorecraft.core.lines.line_at`.

    Args:
        newlines: The offset where each line break in the document's text starts, as `newline_offsets` returns them.
        span: Where the node to locate sits, as `_position` reads it.
    """
    offset = TextOffset(UnsignedInt(span.start))
    return Line(NonZeroUnsignedInt(bisect_left(newlines, offset) + 1))


def _position(node: Node) -> Position:
    """Where a node sits in the document's text, as character offsets.

    Every node `parse_markdown` reads has a position, since its parser is built with `positions=True`. wenmode's
    types cannot say so: positions are a flag the parser takes at runtime, so every node declares its `position`
    optional. This is the one place the module turns that optional into a `Position`, so every other helper that
    needs a node's span reads it here.

    Args:
        node: Node of the full parse tree, which always carries a position.
    """
    if node.position is None:
        # SAFETY: the full parser is built with positions=True, so every node carries its position
        raise Unreachable('a node of the full parser has a position')
    return node.position
