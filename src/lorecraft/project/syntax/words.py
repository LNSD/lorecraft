"""How many prose words a stretch of text holds: the one word rule every word count and word cap uses."""


def count_words(text: str) -> int:
    """The prose words in `text`: its whitespace-delimited tokens.

    A token is any run of characters between whitespace, punctuation and markup included, so `a, b` holds two
    words and `**bold** text` two. Which text counts as prose, such as leaving code blocks and table rows out, is
    the caller's to decide; this only counts.

    Args:
        text: Text to count, of one or more lines; empty or whitespace alone counts as 0.
    """
    return len(text.split())
