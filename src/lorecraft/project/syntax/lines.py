"""How many lines a text holds, and what they are, counted from the raw text without a parse."""

import re
from typing import NewType

from lorecraft.core.num import UnsignedInt

LineCount = NewType('LineCount', UnsignedInt)
"""How many lines a text holds: a count of lines, never taken for a count of tokens or of words."""


def count_lines(text: str) -> LineCount:
    r"""The number of lines in `text`, frontmatter, code and blank lines included, as the findings number them.

    A line ends at a `\n` and nowhere else, as every finding's line number counts it, and as editors and `wc -l`
    do: a `\r\n` ends one line, and a lone `\r`, a form feed or a Unicode line separator inside a line does not end
    it. A last line with no `\n` after it is still a line, and a final `\n` opens none: `'a\nb'` and `'a\nb\n'`
    both hold two lines.

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
    separator, would shift every later line number off the one a rule reported. A `\r` before the `\n` is part of the
    break, not of the line, and a final `\n` opens no line.

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
