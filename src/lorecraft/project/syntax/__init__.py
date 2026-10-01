"""A document's parse tree: the frontmatter node, the headings, the links, and the line positions every check reports
against.

Beside it, ``count_tokens``: what a document's raw text costs an agent, counted without parsing it.
"""

from .document import ParsedDocument, parse_document, parse_frontmatter
from .frontmatter import (
    Frontmatter,
    FrontmatterKey,
    FrontmatterNode,
    InvalidYamlFrontmatter,
    MissingFrontmatter,
    NonMappingFrontmatter,
)
from .heading import Heading
from .link import Link
from .position import InvalidLineNumberError, LineNumber
from .tokens import count_tokens

__all__ = [
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
    'Link',
    'LineNumber',
    'InvalidLineNumberError',
    'count_tokens',
]
