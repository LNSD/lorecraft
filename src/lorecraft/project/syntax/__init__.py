"""A document's parse tree.

It holds the frontmatter node, the headings and their anchors, the links, and the line positions every check
reports against.

Beside it, `count_tokens`: what a document's raw text costs an agent, counted without parsing it, and
`count_lines`: how many lines that raw text holds, counted the same way.
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
from .heading import Heading, HeadingLevel
from .lines import count_lines
from .link import Link
from .position import LineNumber
from .tokens import count_tokens

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
    'Link',
    'Anchor',
    'InvalidAnchorError',
    'LineNumber',
    'count_tokens',
    'count_lines',
]
