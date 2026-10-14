"""How many lines a text holds, and what they are, counted from the raw text without a parse.

This module is the one place that says where a line ends, so code that numbers lines never disagrees with
other code that does, whether it locates a line in text or in the bytes of a file that does not decode.
"""

import re
from typing import NewType

from lorecraft.core.num import UnsignedInt

LineCount = NewType('LineCount', UnsignedInt)
"""How many lines a text holds: a count of lines, never taken for a count of tokens or of words."""


def count_lines(text: str) -> LineCount:
    r"""The number of lines in `text`, blank lines included.

    A line ends at a `\n` and nowhere else, as editors and `wc -l` count it: a `\r\n` ends one line, and a lone
    `\r`, a form feed or a Unicode line separator inside a line does not end it. A last line with no `\n` after
    it is still a line, and a final `\n` opens none: `'a\nb'` and `'a\nb\n'` both hold two lines.

    Args:
        text: Text to count, a whole file; empty counts as 0.
    """
    newlines = text.count('\n')
    # A count is never negative, so building the `UnsignedInt` cannot raise `NegativeIntError` here.
    if text and not text.endswith('\n'):
        return LineCount(UnsignedInt(newlines + 1))
    return LineCount(UnsignedInt(newlines))


def split_lines(text: str) -> tuple[str, ...]:
    r"""The lines of `text`, numbered as `count_lines` counts them, without their line breaks.

    A line ends at a `\n` and nowhere else, so `str.splitlines`, which also breaks at a form feed or a Unicode line
    separator, would shift every later line number off the one `count_lines` gives. A `\r` before the `\n` is part
    of the break, not of the line, and a final `\n` opens no line.

    Args:
        text: Text to split, a whole file; empty holds no line.
    """
    lines = text.split('\n')
    if lines[-1] == '':
        lines.pop()
    return tuple(line.removesuffix('\r') for line in lines)


def newline_offsets(text: str) -> tuple[int, ...]:
    r"""The offset of every line break in `text`, in ascending order, one per `\n`.

    The breaks `count_lines` and `split_lines` end a line at, so the line an offset is on is one more than the number
    of these before it. Built once, a binary search over them locates an offset without counting from the start of
    the text.

    Args:
        text: Text to scan, a whole file.
    """
    return tuple(match.start() for match in re.finditer('\n', text))


def line_at(text: str | bytes, offset: int) -> int:
    r"""The line `offset` is on, from 1, counting the `\n` before it.

    An offset is on the line that its preceding `\n` count gives, so the offset of a `\n` is on the line it ends.
    Takes bytes too, so a file that does not decode is located by the same rule as one that does.

    Args:
        text: Text or the UTF-8 bytes of it, a whole file.
        offset: A character offset into text, or a byte offset into bytes; at most its length.
    """
    if isinstance(text, bytes):
        return text.count(b'\n', 0, offset) + 1
    return text.count('\n', 0, offset) + 1
