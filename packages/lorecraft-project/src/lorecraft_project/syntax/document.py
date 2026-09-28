"""The root of a document's parse tree: what every check reads instead of the document's text.

A parse tree is a pure function of the text, so a document is parsed once and every check shares the result.
The Markdown parser is wenmode, and this module is the only place it is used: its nodes are mutable and its API
is pre-1.0, so what leaves here is always this package's own frozen nodes, never a wenmode type. Only the
frontmatter is kept so far; the headings and their sections join as sibling fields when a check needs them.

A check that reads nothing but the frontmatter does not need the tree: ``parse_frontmatter`` finds and decodes
the same block for a fraction of the cost, so it is the cheap path, and ``parse_document`` the full one.
"""

from dataclasses import dataclass
from typing import Final

from wenmode import Wenmode
from wenmode.nodes import Root
from wenmode.plugins import frontmatter
from wenmode.plugins.frontmatter import FrontmatterPlugin

from .frontmatter import FrontmatterNode, MissingFrontmatter, decode_frontmatter

_FRONTMATTER_KEY: Final[str] = 'frontmatter'
"""Where wenmode's frontmatter plugin stores the decoded block on the root node's ``data``."""


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    """One document's parse tree.

    Not hashable when its frontmatter holds a mapping, since ``Frontmatter`` holds a dict.

    Attributes:
        frontmatter: The frontmatter block, or the reason there is no usable one.
    """

    frontmatter: FrontmatterNode


def parse_document(text: str) -> ParsedDocument:
    """Parse one document's text into its parse tree. Pure: raises nothing.

    The frontmatter block is found by wenmode's frontmatter plugin: a ``---`` line as the document's first line,
    closed by the next ``---`` line, each allowing trailing whitespace only. The plugin hands the lines between
    them to ``decode_frontmatter``, which never raises, so a broken block cannot fail the parse. A document with
    no such block has ``MissingFrontmatter``.
    """
    # A parser is built per call rather than shared: wenmode parsers are mutable, and one costs a small fraction
    # of what parsing a document does.
    markdown = Wenmode(plugins=[_frontmatter_plugin()])
    return ParsedDocument(frontmatter=_frontmatter(markdown.parse(text)))


def parse_frontmatter(text: str) -> FrontmatterNode:
    """Parse only the frontmatter block of one document's text. Pure: raises nothing.

    Equal to ``parse_document(text).frontmatter`` for every text. The block is found by the same wenmode plugin,
    and the plugin only ever claims the document's first line, where it is tried before every Markdown rule, so
    what it finds does not depend on the rules. This parser loads none of them: the rest of the text is read as
    plain paragraphs, which costs a small fraction of the full parse.
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
