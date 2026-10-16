"""The Markdown syntax Lorecraft reads, and the one package that imports wenmode.

A document's text is read here into frozen values of this package's own: its top-level blocks, the text each heading
renders as, its links, and the raw frontmatter block. What a document, an anchor or a link means is derived from them
in `lorecraft.project`.
"""

from .parser import (
    ContentBlock,
    HeadingBlock,
    HeadingLevel,
    MarkdownLine,
    MarkdownLink,
    MarkdownTree,
    parse_markdown,
    parse_markdown_frontmatter,
)

__all__ = [
    'ContentBlock',
    'HeadingBlock',
    'HeadingLevel',
    'MarkdownLine',
    'MarkdownLink',
    'MarkdownTree',
    'parse_markdown',
    'parse_markdown_frontmatter',
]
