"""A document's parse tree.

It holds the frontmatter node, the headings and their anchors, the links, and the line positions every check
reports against. `find_title` finds a document's title among its headings, and `find_sections` its H2 sections as
`SectionHeading` values.

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
    reads_back_as_string,
)
from .heading import Heading, HeadingLevel, SectionHeading, find_sections, find_title
from .lines import LineCount, count_lines, split_lines
from .link import (
    AbsoluteDestination,
    ExternalDestination,
    FragmentDestination,
    Link,
    LinkDestination,
    NormalisedLinkPath,
    RelativeDestination,
)
from .position import LineNumber
from .tokens import TokenCount, count_tokens
from .words import WordCount, count_words

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
    'reads_back_as_string',
    'Heading',
    'HeadingLevel',
    'SectionHeading',
    'find_sections',
    'find_title',
    'Link',
    'LinkDestination',
    'ExternalDestination',
    'AbsoluteDestination',
    'FragmentDestination',
    'RelativeDestination',
    'NormalisedLinkPath',
    'Anchor',
    'InvalidAnchorError',
    'LineNumber',
    'TokenCount',
    'count_tokens',
    'LineCount',
    'count_lines',
    'split_lines',
    'WordCount',
    'count_words',
]
