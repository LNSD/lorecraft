r"""How many lines a text holds, and what they are, counted from the raw text without a parse.

A line ends where CommonMark ends it: at a `\n`, at a `\r\n` as one break, and at a lone `\r`. Nothing else ends
one, so a vertical tab, a form feed, U+0085 and the Unicode line and paragraph separators stay inside their line.
This module is the one place that says so, so code that numbers lines, in text or in the bytes of a file that does
not decode, never disagrees with other code that does.
"""

import re
from bisect import bisect_right
from typing import Final, NewType

from .num import NonZeroUnsignedInt, UnsignedInt

LineCount = NewType('LineCount', UnsignedInt)
"""How many lines a text holds: a count of lines, never taken for a count of tokens or of words."""

Line = NewType('Line', NonZeroUnsignedInt)
"""A one-based line number, never taken for another count."""

LineOffset = NewType('LineOffset', UnsignedInt)
"""A zero-based line offset, for formats that number lines from 0."""

ByteOffset = NewType('ByteOffset', UnsignedInt)
"""A zero-based offset into bytes, never negative."""

TextOffset = NewType('TextOffset', UnsignedInt)
"""A zero-based offset into text, never negative."""

_BREAK: Final[re.Pattern[str]] = re.compile(r'\r\n?|\n')
"""A line break in text: a `\\r\\n` pair as one break, a lone `\\r` or a `\\n`."""

_BREAK_IN_BYTES: Final[re.Pattern[bytes]] = re.compile(rb'\r\n?|\n')
"""A line break in UTF-8 bytes, which breaks lines at the same bytes as the text they decode to."""


def count_lines(text: str) -> LineCount:
    r"""The number of lines in `text`, blank lines included.

    A last line with no line break after it is still a line, and a final line break opens none: `'a\nb'` and
    `'a\nb\n'` both hold two lines, and so do `'a\rb'` and `'a\r\nb\r\n'`.

    Args:
        text: Text to count, a whole file; empty counts as 0.
    """
    breaks = len(_BREAK.findall(text))
    # A count is never negative, so building the `UnsignedInt` cannot raise `NegativeIntError` here.
    if text and not text.endswith(('\n', '\r')):
        return LineCount(UnsignedInt(breaks + 1))
    return LineCount(UnsignedInt(breaks))


def split_lines(text: str) -> tuple[str, ...]:
    r"""The lines of `text`, numbered as `count_lines` counts them, without their line breaks.

    A `\r\n` is one break, so the `\r` is no part of a line, and a final break opens no line.

    Args:
        text: Text to split, a whole file; empty holds no line.
    """
    lines = _BREAK.split(text)
    if lines[-1] == '':
        lines.pop()
    return tuple(lines)


def newline_offsets(text: str) -> tuple[TextOffset, ...]:
    r"""The offset where each line break in `text` starts, in ascending order.

    The line an offset is on is one more than the number of these before it, so a binary search over them locates an
    offset without counting from the start of the text. A `\r\n` is one break, starting at its `\r`.

    Args:
        text: Text to scan, a whole file.
    """
    return tuple(TextOffset(UnsignedInt(match.start())) for match in _BREAK.finditer(text))


def line_at(text: str | bytes, offset: TextOffset | ByteOffset) -> Line:
    r"""The line `offset` is on, from 1: one more than the number of line breaks that end at or before it.

    An offset between the `\r` and the `\n` of a pair is still on the line the pair ends, and the offset of a break's
    first character is on the line that break ends. A search over `newline_offsets` counts a break once its first
    character is before the offset instead, which agrees wherever an offset starts a token. Takes bytes too, so a
    file that does not decode is located by the same rule as one that does.

    Args:
        text: Text or the UTF-8 bytes of it, a whole file.
        offset: A character offset into text, or a byte offset into bytes; at most its length.
    """
    if isinstance(text, bytes):
        ends = [match.end() for match in _BREAK_IN_BYTES.finditer(text)]
    else:
        ends = [match.end() for match in _BREAK.finditer(text)]
    return Line(NonZeroUnsignedInt(bisect_right(ends, offset.value) + 1))
