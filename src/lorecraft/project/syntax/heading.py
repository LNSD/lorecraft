"""The heading nodes of a document's parse tree: the document's own top-level headings, in document order.

Only headings that section the document itself are kept. One quoted in a blockquote or nested in a list item
illustrates a document rather than sectioning this one, and a `#` line inside a fenced code block is code,
not a heading; the Markdown parser decides both (see `markdown`).
"""

from dataclasses import dataclass
from typing import Final, Literal

from .position import LineNumber
from .words import WordCount

type HeadingLevel = Literal[1, 2, 3, 4, 5, 6]
"""A heading's depth: 1 for a title through 6, the deepest Markdown has."""

_SECTION_LEVEL: Final[HeadingLevel] = 2
"""The heading level of a section: H1 is the title, and anything deeper is a subsection."""


@dataclass(frozen=True, slots=True)
class Heading:
    """One top-level heading, whether the section it opens holds any content, and how many prose words.

    Attributes:
        level: The heading depth, 1 for a title through 6.
        text: The heading's plain text, inline markup stripped, so `**Checklist**` reads `Checklist`.
        line: The document line the heading starts on.
        empty: True when nothing follows the heading before the next heading of the same or a higher level,
            or before the end of the document. A deeper heading opens a subsection, which is content.
        words: The prose words in the section the heading opens, up to the same boundary as `empty`: a
            subsection's prose counts toward it, and no heading's own text does. Code blocks and table rows
            are not prose.
    """

    level: HeadingLevel
    text: str
    line: LineNumber
    empty: bool
    words: WordCount


@dataclass(frozen=True, slots=True)
class SectionHeading:
    """The heading of one section of a document.

    It is told apart from a title or a subsection heading by its type, so a reader of an alignment cannot be handed
    a heading that opens no section. Only `section_headings` builds one, and for now only from H2 headings; the level
    is kept so that nested sections can follow.

    Attributes:
        level: The heading depth, 1 for a title through 6.
        text: The heading's plain text, as `Heading.text`.
        line: The document line the heading starts on.
        empty: True when nothing follows the heading before the next heading of the same or a higher level, as
            `Heading.empty`.
        words: The prose words in the section the heading opens, as `Heading.words`.
    """

    level: HeadingLevel
    text: str
    line: LineNumber
    empty: bool
    words: WordCount


def section_headings(headings: tuple[Heading, ...]) -> tuple[SectionHeading, ...]:
    """A document's sections, in document order, which are its H2 headings for now. Raises nothing.

    Args:
        headings: The document's top-level headings, of every level, in document order.
    """
    return tuple(
        SectionHeading(
            level=heading.level, text=heading.text, line=heading.line, empty=heading.empty, words=heading.words
        )
        for heading in headings
        if heading.level == _SECTION_LEVEL
    )


def find_title(headings: tuple[Heading, ...]) -> Heading | None:
    """A document's title: its first H1 heading, or `None` when it has none. Raises nothing.

    A later H1 is a second title, which is a finding of its own, so no check on the title is held against it.

    Args:
        headings: The document's top-level headings, in document order.
    """
    for heading in headings:
        if heading.level == 1:
            return heading
    return None
