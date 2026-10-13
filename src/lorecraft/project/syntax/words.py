"""How many prose words a stretch of text holds: the one word rule every word count and word cap uses."""

from typing import NewType

from lorecraft.core.num import UnsignedInt

WordCount = NewType('WordCount', UnsignedInt)
"""How many prose words a text holds: a count of words, never taken for a count of tokens or of lines."""


def count_words(text: str) -> WordCount:
    """The prose words in `text`: its whitespace-delimited tokens.

    A token is any run of characters between whitespace, punctuation and markup included, so `a, b` holds two
    words and `**bold** text` two. Which text counts as prose, such as leaving code blocks and table rows out, is
    the caller's to decide; this only counts.

    Args:
        text: Text to count, of one or more lines; empty or whitespace alone counts as 0.
    """
    # A count is never negative, so building the `UnsignedInt` cannot raise `NegativeIntError` here.
    return WordCount(UnsignedInt(len(text.split())))
