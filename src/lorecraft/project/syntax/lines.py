"""How many lines a text holds, counted from the raw text without a parse."""


def count_lines(text: str) -> int:
    r"""The number of lines in `text`, frontmatter, code and blank lines included, as the findings number them.

    A line ends at a `\n` and nowhere else, as every finding's line number counts it, and as editors and `wc -l`
    do: a `\r\n` ends one line, and a lone `\r`, a form feed or a Unicode line separator inside a line does not end
    it. A last line with no `\n` after it is still a line, and a final `\n` opens none: `'a\nb'` and `'a\nb\n'`
    both hold two lines.

    Args:
        text: Text to count, a whole file; empty counts as 0.
    """
    newlines = text.count('\n')
    if text and not text.endswith('\n'):
        return newlines + 1
    return newlines
