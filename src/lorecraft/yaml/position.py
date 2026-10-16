"""Where an index into a YAML text is, as a one-based line and column counted in the characters of the text.

ruamel.yaml counts a mark's column without U+FEFF, so a column read from a mark drifts from the characters of the text
wherever a byte order mark is written past the first line start. The index of a mark does not drift, so every position
is computed from it and the text.
"""

import re
from bisect import bisect_right
from typing import Final

from lorecraft.core.num import NonZeroUnsignedInt

from .tree import YamlPosition

_BREAK: Final[re.Pattern[str]] = re.compile(r'\r\n?|\n')
"""A line break as `core/lines.py` counts it, which the reader of this package follows: `\\r\\n`, `\\r` or `\\n`."""


class LineIndex:
    """Where each line of one YAML text starts, so an index into the text is located by a binary search.

    One index belongs to one read of one text and is dropped with it.
    """

    def __init__(self, text: str) -> None:
        """Scan the line breaks of `text` once.

        Args:
            text: The YAML text.
        """
        self._starts = (0, *(match.end() for match in _BREAK.finditer(text)))

    def position_at(self, index: int) -> YamlPosition:
        """The position of the character at `index`.

        Args:
            index: A character offset into the text, from 0; at most its length.
        """
        line = bisect_right(self._starts, index)
        return YamlPosition(NonZeroUnsignedInt(line), NonZeroUnsignedInt(index - self._starts[line - 1] + 1))
