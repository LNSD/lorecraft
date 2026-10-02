"""The root of a document's parse tree: what every check reads instead of the document's text.

A parse tree is a pure function of the text, so a document is parsed once and every check shares the result.
The Markdown parser is wenmode, and this module is the only place it is used: its nodes are mutable and its API
is pre-1.0, so what leaves here is always this package's own frozen nodes, never a wenmode type. The tree keeps
the frontmatter, the document's top-level headings, how many prose words each heading's section holds, the anchor
of every heading at any depth, and every link's destination and line. The rest of the content is not kept: no check
reads it yet.

A heading's anchor is the name a fragment-only link such as ``#usage`` points at. ``Anchor`` derives it from the
heading's text as GitHub does; what is read here is which headings take one, the text GitHub renders each from,
and how a repeat is numbered.

A prose word is whitespace-delimited text outside code blocks, table rows and headings: a section's words say how
concise its prose is, and code and tables are free because they are the examples and references a document exists
to hold. What the whole file costs an agent that loads it is a different question, answered from the raw text by
``count_tokens`` without a parse.

A check that reads nothing but the frontmatter does not need the tree: ``parse_frontmatter`` finds and decodes
the same block for a fraction of the cost, so it is the cheap path, and ``parse_document`` the full one.
"""

from dataclasses import dataclass
from typing import Final

from wenmode import Wenmode
from wenmode.ast import plain_text
from wenmode.nodes import Code, Html, Image, Literal, Node, Parent, Position, Root
from wenmode.nodes import Heading as WenmodeHeading
from wenmode.nodes import Link as WenmodeLink
from wenmode.plugins import frontmatter
from wenmode.plugins.frontmatter import FrontmatterPlugin

from .anchor import Anchor
from .frontmatter import FrontmatterNode, MissingFrontmatter, decode_frontmatter
from .heading import Heading, HeadingLevel
from .link import Link
from .position import LineNumber

_FRONTMATTER_KEY: Final[str] = 'frontmatter'
"""Where wenmode's frontmatter plugin stores the decoded block on the root node's ``data``."""


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    """One document's parse tree.

    Not hashable when its frontmatter holds a mapping, since ``Frontmatter`` holds a dict.

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

    The frontmatter block is found by wenmode's frontmatter plugin: a ``---`` line as the document's first line,
    closed by the next ``---`` line, each allowing trailing whitespace only. The plugin hands the lines between
    them to `decode_frontmatter`, which never raises, so a broken block cannot fail the parse. A document with
    no such block has `MissingFrontmatter`.

    Args:
        text: The document's whole text, frontmatter block included; empty parses to a document with none.
    """
    # A parser is built per call rather than shared: wenmode parsers are mutable, and one costs a small fraction
    # of what parsing a document does.
    markdown = Wenmode(plugins=[_frontmatter_plugin()], positions=True)
    root = markdown.parse(text)
    block_words = [_prose_words(text, block) for block in root.children]
    return ParsedDocument(
        frontmatter=_frontmatter(root),
        headings=_headings(text, root.children, block_words),
        anchors=_anchors(root),
        links=tuple(_links(text, root)),
    )


def parse_frontmatter(text: str) -> FrontmatterNode:
    """Parse only the frontmatter block of one document's text. Pure: raises nothing.

    Equal to `parse_document(text).frontmatter` for every text. The block is found by the same wenmode plugin,
    and the plugin only ever claims the document's first line, where it is tried before every Markdown rule, so
    what it finds does not depend on the rules. This parser loads none of them: the rest of the text is read as plain
    paragraphs, which costs a small fraction of the full parse.

    Args:
        text: The document's whole text, frontmatter block included.
    """
    markdown = Wenmode(rules=(), plugins=[_frontmatter_plugin()])
    return _frontmatter(markdown.parse(text))


def _frontmatter_plugin() -> FrontmatterPlugin:
    """The frontmatter plugin of wenmode, decoding the block with ``decode_frontmatter`` into the root's data."""
    return frontmatter.configure(load=decode_frontmatter, data_key=_FRONTMATTER_KEY)


def _frontmatter(root: Root) -> FrontmatterNode:
    """The frontmatter node the plugin left on a parsed root, or `MissingFrontmatter` when it found no block.

    Args:
        root: Root of a tree parsed with the frontmatter plugin; its `data` holds the decoded block, if any.
    """
    if root.data is None or _FRONTMATTER_KEY not in root.data:
        return MissingFrontmatter()
    # The plugin stores whatever its loader returned, and the loader is `decode_frontmatter`.
    decoded: FrontmatterNode = root.data[_FRONTMATTER_KEY]
    return decoded


def _headings(text: str, blocks: list[Node], block_words: list[int]) -> tuple[Heading, ...]:
    """The headings among the root's own blocks, each with its line, its section's words and whether it is empty.

    Only the root's children are read, never the whole tree: a heading inside a blockquote or a list item is a
    child of that block, so it is left out without being looked for.

    Args:
        text: The document's text, which the blocks' positions index into.
        blocks: The root's own blocks, in document order.
        block_words: The prose words of each block, at the same index as the block.
    """
    headings: list[Heading] = []
    for index, block in enumerate(blocks):
        if not isinstance(block, WenmodeHeading):
            continue
        following = blocks[index + 1] if index + 1 < len(blocks) else None
        # A section is empty when the next block closes it: the end of the document, or a heading of the same
        # or a higher level. A deeper heading opens a subsection, whose content is this section's own.
        empty = following is None or (isinstance(following, WenmodeHeading) and following.depth <= block.depth)
        headings.append(
            Heading(
                level=_heading_level(block.depth),
                text=plain_text(block.children),
                line=_line(text, _position(block)),
                empty=empty,
                words=_section_words(blocks, block_words, index, block.depth),
            )
        )
    return tuple(headings)


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


def _anchors(root: Root) -> frozenset[Anchor]:
    """The anchor GitHub gives each heading in the document, a repeated one numbered as GitHub numbers it.

    The whole tree is read, unlike for ``_headings``: a heading in a list item or a blockquote still renders with
    an anchor a link can name. Headings take their anchors in document order. The first heading to take an anchor
    keeps it bare; the next one with the same anchor gets `-1` added, the one after that `-2`, and so on. A
    numbered anchor another heading already holds is skipped, so `Foo 1`, `Foo`, `Foo` give `foo-1`,
    `foo` and `foo-2`: no two headings share an anchor.

    Args:
        root: Root of the parsed document, whose whole tree is read.
    """
    # Every anchor taken so far, each mapped to how many times it has been numbered as a bare anchor.
    occurrences: dict[Anchor, int] = {}
    for heading in _heading_nodes(root):
        bare = Anchor.from_heading(_rendered_text(heading.children))
        anchor = bare
        while anchor in occurrences:
            occurrences[bare] += 1
            anchor = bare.numbered(occurrences[bare])
        occurrences[anchor] = 0
    return frozenset(occurrences)


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


def _heading_nodes(node: Node) -> list[WenmodeHeading]:
    """Every wenmode heading in the node and below it, the node itself included, in document order.

    Args:
        node: Root of the subtree to search; a leaf is searched as itself.
    """
    headings: list[WenmodeHeading] = []
    if isinstance(node, WenmodeHeading):
        headings.append(node)
    if isinstance(node, Parent):
        for child in node.children:
            headings.extend(_heading_nodes(child))
    return headings


def _links(text: str, node: Node) -> list[Link]:
    """Every link and image in the node and below it, the node itself included, in document order.

    The whole tree is walked, unlike for the headings: a link in a list item or a blockquote is as much the
    document's as one in a top-level paragraph. An image inside a link's text comes after that link.

    Args:
        text: The document's text, which the nodes' positions index into to give each link its line.
        node: Root of the subtree to search; a leaf is searched as itself.
    """
    links: list[Link] = []
    if isinstance(node, WenmodeLink | Image):
        links.append(Link(url=node.url, line=_line(text, _position(node))))
    if isinstance(node, Parent):
        for child in node.children:
            links.extend(_links(text, child))
    return links


def _section_words(blocks: list[Node], block_words: list[int], heading_index: int, level: int) -> int:
    """The prose words in the section a heading opens, its subsections' included.

    The section runs to the next heading of the same or a higher level, or to the end of the document. A deeper
    heading does not close it, and holds no prose words of its own, so adding every block's words is enough.

    Args:
        blocks: The root's own blocks, in document order.
        block_words: The prose words of each block, at the same index as the block.
        heading_index: Where the heading opening the section sits in ``blocks``.
        level: That heading's depth.
    """
    words = 0
    for index in range(heading_index + 1, len(blocks)):
        block = blocks[index]
        if isinstance(block, WenmodeHeading) and block.depth <= level:
            break
        words += block_words[index]
    return words


def _prose_words(text: str, block: Node) -> int:
    """The prose words one of the root's blocks holds: whitespace-delimited tokens of its source text.

    A heading and a code block, fenced or indented, hold none, and neither does a code block nested in the block,
    such as one inside a list item. The rest is counted from its source text rather than from its parsed inlines,
    so a link counts as the words its source is written with.

    Args:
        text: The document's text, which the block's position indexes into.
        block: One of the root's own blocks, in the tree `parse_document` parsed.
    """
    if isinstance(block, WenmodeHeading):
        return 0
    span = _position(block)
    words = 0
    start = span.start
    for code in _code_spans(block):
        words += _source_words(text[start : code.start])
        start = code.end
    words += _source_words(text[start : span.end])
    return words


def _code_spans(node: Node) -> list[Position]:
    """Where each code block in the node sits, the node itself included, in document order.

    A code block holds text, never another block, so no span found here contains another.

    Args:
        node: Root of the subtree to search, in the tree `parse_document` parsed; a leaf is searched as itself.
    """
    if isinstance(node, Code):
        return [_position(node)]
    if not isinstance(node, Parent):
        return []
    spans: list[Position] = []
    for child in node.children:
        spans.extend(_code_spans(child))
    return spans


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


def _line(text: str, span: Position) -> LineNumber:
    r"""The document line a node's span starts on, a block's or an inline's alike.

    wenmode reports a node's position as a character offset into the text; every line before the offset ends in
    a `\n`, a `\r\n` included.

    Args:
        text: The document's text, which the span indexes into.
        span: Where the node to locate sits, as `_position` reads it.
    """
    return LineNumber(text.count('\n', 0, span.start) + 1)


def _position(node: Node) -> Position:
    """Where a node sits in the document's text, as character offsets.

    Every node `parse_document` reads has a position, since it builds its parser with `positions=True`. wenmode's
    types cannot say so: positions are a flag the parser takes at runtime, so every node declares its `position`
    optional. This is the one place the module turns that optional into a `Position`, so every other helper that
    needs a node's span reads it here.

    Args:
        node: Node of the tree `parse_document` parsed. A tree from any other parser, such as
            `parse_frontmatter`'s, may lack positions.
    """
    if node.position is None:
        raise AssertionError('unreachable: parse_document builds its parser with positions=True')
    return node.position
