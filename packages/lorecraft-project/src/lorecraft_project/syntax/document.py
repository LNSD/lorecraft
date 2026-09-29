"""The root of a document's parse tree: what every check reads instead of the document's text.

A parse tree is a pure function of the text, so a document is parsed once and every check shares the result.
The Markdown parser is wenmode, and this module is the only place it is used: its nodes are mutable and its API
is pre-1.0, so what leaves here is always this package's own frozen nodes, never a wenmode type. The tree keeps
the frontmatter, the document's top-level headings, and how many prose words each heading's section holds. The
content itself is not kept: no check reads it yet.

A prose word is whitespace-delimited text outside code blocks, table rows and headings: a section's words say how
concise its prose is, and code and tables are free because they are the examples and references a document exists
to hold.

A check that reads nothing but the frontmatter does not need the tree: ``parse_frontmatter`` finds and decodes
the same block for a fraction of the cost, so it is the cheap path, and ``parse_document`` the full one.
"""

from dataclasses import dataclass
from typing import Final

from wenmode import Wenmode
from wenmode.ast import plain_text
from wenmode.nodes import Code, Node, Parent, Position, Root
from wenmode.nodes import Heading as WenmodeHeading
from wenmode.plugins import frontmatter
from wenmode.plugins.frontmatter import FrontmatterPlugin

from .frontmatter import FrontmatterNode, MissingFrontmatter, decode_frontmatter
from .heading import Heading
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
    """

    frontmatter: FrontmatterNode
    headings: tuple[Heading, ...]


def parse_document(text: str) -> ParsedDocument:
    """Parse one document's text into its parse tree. Pure: raises nothing.

    The frontmatter block is found by wenmode's frontmatter plugin: a ``---`` line as the document's first line,
    closed by the next ``---`` line, each allowing trailing whitespace only. The plugin hands the lines between
    them to ``decode_frontmatter``, which never raises, so a broken block cannot fail the parse. A document with
    no such block has ``MissingFrontmatter``.
    """
    # A parser is built per call rather than shared: wenmode parsers are mutable, and one costs a small fraction
    # of what parsing a document does.
    markdown = Wenmode(plugins=[_frontmatter_plugin()], positions=True)
    root = markdown.parse(text)
    block_words = [_prose_words(text, block) for block in root.children]
    return ParsedDocument(frontmatter=_frontmatter(root), headings=_headings(text, root.children, block_words))


def parse_frontmatter(text: str) -> FrontmatterNode:
    """Parse only the frontmatter block of one document's text. Pure: raises nothing.

    Equal to ``parse_document(text).frontmatter`` for every text. The block is found by the same wenmode plugin,
    and the plugin only ever claims the document's first line, where it is tried before every Markdown rule, so
    what it finds does not depend on the rules. This parser loads none of them: the rest of the text is read as plain
    paragraphs, which costs a small fraction of the full parse.
    """
    markdown = Wenmode(rules=(), plugins=[_frontmatter_plugin()])
    return _frontmatter(markdown.parse(text))


def _frontmatter_plugin() -> FrontmatterPlugin:
    """wenmode's frontmatter plugin, decoding the block with ``decode_frontmatter`` into the root's data."""
    return frontmatter.configure(load=decode_frontmatter, data_key=_FRONTMATTER_KEY)


def _frontmatter(root: Root) -> FrontmatterNode:
    """The frontmatter node the plugin left on a parsed root, or ``MissingFrontmatter`` when it found no block."""
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
                level=block.depth,
                text=plain_text(block.children),
                line=_line(text, block),
                empty=empty,
                words=_section_words(blocks, block_words, index, block.depth),
            )
        )
    return tuple(headings)


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
    """
    if isinstance(block, WenmodeHeading) or block.position is None:
        return 0
    words = 0
    start = block.position.start
    for code in _code_spans(block):
        words += _source_words(text[start : code.start])
        start = code.end
    words += _source_words(text[start : block.position.end])
    return words


def _code_spans(node: Node) -> list[Position]:
    """Where each code block in the node sits, the node itself included, in document order.

    A code block holds text, never another block, so no span found here contains another.
    """
    if isinstance(node, Code):
        return [] if node.position is None else [node.position]
    if not isinstance(node, Parent):
        return []
    spans: list[Position] = []
    for child in node.children:
        spans.extend(_code_spans(child))
    return spans


def _source_words(source: str) -> int:
    """The whitespace-delimited tokens of a stretch of Markdown source, table rows left out."""
    words = 0
    for line in source.splitlines():
        # The parser has no table extension, so a table is read as a paragraph of `|` lines. Those lines are
        # skipped here: a table is a reference, not prose.
        if line.strip().startswith('|'):
            continue
        words += len(line.split())
    return words


def _line(text: str, block: Node) -> LineNumber:
    """The document line a block starts on.

    wenmode reports a block's position as a character offset into the text; every line before the offset ends in
    a ``\\n``, a ``\\r\\n`` included.
    """
    if block.position is None:
        # Unreachable while the parser is built with `positions=True`, which sets every block's position; the
        # field is optional in wenmode's type only because a parser without it leaves it unset.
        return LineNumber(1)
    return LineNumber(text.count('\n', 0, block.position.start) + 1)
