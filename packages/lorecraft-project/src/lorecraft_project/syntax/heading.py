"""The heading nodes of a document's parse tree: the document's own top-level headings, in document order.

Only headings that section the document itself are kept. One quoted in a blockquote or nested in a list item
illustrates a document rather than sectioning this one, and a ``#`` line inside a fenced code block is code,
not a heading; the Markdown parser decides both (see ``document``).
"""

from dataclasses import dataclass

from .position import LineNumber


@dataclass(frozen=True, slots=True)
class Heading:
    """One top-level heading and whether the section it opens holds any content.

    Attributes:
        level: The heading depth, 1 for a title through 6.
        text: The heading's plain text, inline markup stripped, so ``**Checklist**`` reads ``Checklist``.
        line: The document line the heading starts on.
        empty: True when nothing follows the heading before the next heading of the same or a higher level,
            or before the end of the document. A deeper heading opens a subsection, which is content.
    """

    level: int
    text: str
    line: LineNumber
    empty: bool
