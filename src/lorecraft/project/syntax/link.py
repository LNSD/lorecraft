"""The link nodes of a document's parse tree: every link and image the document's text holds, in document order.

A link's destination is kept as the parser reads it, never resolved: what it may point at is a check's question,
not the parser's. Which text is a link the Markdown parser decides (see ``document``): a ``[text](url)`` inside
inline code or a code block is code, not a link, and a reference-style ``[text][label]`` is a link at the place it
is used, with the destination its definition gives.
"""

from dataclasses import dataclass

from .position import LineNumber


@dataclass(frozen=True, slots=True)
class Link:
    """One link or image in a document.

    Attributes:
        url: The destination, an image's source included, as CommonMark reads it: escapes and character
            references decoded, then percent-encoded, so ``[x](</a b>)`` arrives as ``/a%20b``. Never
            resolved against a path.
        line: The document line the link starts on, where it is used rather than where a reference-style
            link's definition sits.
    """

    url: str
    line: LineNumber
