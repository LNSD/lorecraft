"""A document's parse tree.

It holds the frontmatter node, the headings and their anchors, the links, and the line positions every check
reports against. `find_title` finds a document's title among its headings, and `section_headings` its H2 sections as
`SectionHeading` values.

Beside it, `count_tokens`: what a document's raw text costs an agent, counted without parsing it,
`count_lines`: how many lines that raw text holds, counted the same way, and `count_words`: the prose words in a
stretch of text, the one word rule the tree's section word counts are made of.
"""

from lorecraft.core.lines import LineCount, count_lines, split_lines

from .anchor import Anchor, AnchorNumber
from .document import ParsedDocument, parse_document, parse_frontmatter
from .frontmatter import (
    Frontmatter,
    FrontmatterKey,
    FrontmatterNode,
    InvalidYamlFrontmatter,
    MissingFrontmatter,
    NonMappingFrontmatter,
    RepeatedKey,
    is_string_when_read_back,
)
from .heading import Heading, HeadingLevel, SectionHeading, find_title, section_headings
from .link import (
    AbsoluteDestination,
    ExternalDestination,
    FragmentDestination,
    Link,
    NormalisedLinkPath,
    RelativeDestination,
)
from .position import FIRST_LINE, LineNumber
from .tokens import TokenCount, count_tokens
from .words import WordCount, count_words

__all__: list[str] = [
    'ParsedDocument',
    'parse_document',
    'parse_frontmatter',
    'FrontmatterNode',
    'Frontmatter',
    'FrontmatterKey',
    'RepeatedKey',
    'MissingFrontmatter',
    'InvalidYamlFrontmatter',
    'NonMappingFrontmatter',
    'is_string_when_read_back',
    'Heading',
    'HeadingLevel',
    'SectionHeading',
    'section_headings',
    'find_title',
    'Link',
    'ExternalDestination',
    'AbsoluteDestination',
    'FragmentDestination',
    'RelativeDestination',
    'NormalisedLinkPath',
    'Anchor',
    'AnchorNumber',
    'LineNumber',
    'FIRST_LINE',
    'TokenCount',
    'count_tokens',
    'LineCount',
    'count_lines',
    'split_lines',
    'WordCount',
    'count_words',
]
