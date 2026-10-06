"""The heading nodes of a document's parse tree: the document's own top-level headings, in document order.

Only headings that section the document itself are kept. One quoted in a blockquote or nested in a list item
illustrates a document rather than sectioning this one, and a `#` line inside a fenced code block is code,
not a heading; the Markdown parser decides both (see `markdown`).
"""

from dataclasses import dataclass
from typing import Final, Literal, assert_never

from .position import LineNumber

type HeadingLevel = Literal[1, 2, 3, 4, 5, 6]
"""A heading's depth: 1 for a title through 6, the deepest Markdown has."""

SECTION_LEVEL: Final[int] = 2
"""The heading level of a section: H1 is the title, and anything deeper is a subsection."""


@dataclass(frozen=True, slots=True)
class Heading:
    """One top-level heading, whether the section it opens holds any content, and how many prose words.

    Attributes:
        level: The heading depth, 1 for a title through 6.
        text: The heading's plain text, inline markup stripped, so ``**Checklist**`` reads ``Checklist``.
        line: The document line the heading starts on.
        empty: True when nothing follows the heading before the next heading of the same or a higher level,
            or before the end of the document. A deeper heading opens a subsection, which is content.
        words: The prose words in the section the heading opens, up to the same boundary as ``empty``: a
            subsection's prose counts toward it, and no heading's own text does. Code blocks and table rows
            are not prose.
    """

    level: HeadingLevel
    text: str
    line: LineNumber
    empty: bool
    # Not range-checked: only `document.parse_document` builds a heading, from the words it counts, so the value
    # is never below 0.
    words: int

    def __post_init__(self) -> None:
        """Fail on a level outside 1 to 6, which the type rules out but cannot stop at run time.

        The type is checked only before the code runs, so a value that reached `level` through `Any` or a `cast`
        is caught here instead.

        Raises:
            AssertionError: If `level` is not in 1..6.
        """
        match self.level:
            case 1 | 2 | 3 | 4 | 5 | 6:
                pass
            case _:
                assert_never(self.level)
