"""A document's parse tree.

It holds the frontmatter node, the headings and their anchors, the links, and the line positions every check
reports against.

Beside it, `count_tokens`: what a document's raw text costs an agent, counted without parsing it,
`count_lines`: how many lines that raw text holds, counted the same way, and `count_words`: the prose words in a
stretch of text, the one word rule the tree's section word counts are made of.
"""

from .anchor import Anchor, InvalidAnchorError
from .document import ParsedDocument, parse_document, parse_frontmatter
from .frontmatter import (
    Frontmatter,
    FrontmatterKey,
    FrontmatterNode,
    InvalidYamlFrontmatter,
    MissingFrontmatter,
    NonMappingFrontmatter,
)
from .heading import SECTION_LEVEL, Heading, HeadingLevel
from .lines import count_lines
from .link import Link
from .position import LineNumber
from .tokens import count_tokens
from .words import count_words

__all__: list[str] = [
    'ParsedDocument',
    'parse_document',
    'parse_frontmatter',
    'FrontmatterNode',
    'Frontmatter',
    'FrontmatterKey',
    'MissingFrontmatter',
    'InvalidYamlFrontmatter',
    'NonMappingFrontmatter',
    'Heading',
    'HeadingLevel',
    'SECTION_LEVEL',
    'Link',
    'Anchor',
    'InvalidAnchorError',
    'LineNumber',
    'count_tokens',
    'count_lines',
    'count_words',
]
