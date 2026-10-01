"""The link nodes of a document's parse tree: every link and image the document's text holds, in document order.

A link's destination is kept as the parser reads it, never resolved: what it may point at is a check's question,
not the parser's. Which text is a link the Markdown parser decides (see `document`): a `[text](url)` inside
inline code or a code block is code, not a link, and a reference-style `[text][label]` is a link at the place it
is used, with the destination its definition gives.

What path a destination spells is the parse tree's to tell, though: `Link.to_relative_path` reads it once, so
every check that follows a link reads the same path from it.
"""

import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Final
from urllib.parse import unquote

from .position import LineNumber

_SCHEME: Final[re.Pattern[str]] = re.compile(r'[A-Za-z][A-Za-z0-9+.-]*:')
"""The scheme a URL starts with, such as `https:` or `mailto:`, as RFC 3986 spells one."""


@dataclass(frozen=True, slots=True)
class Link:
    """One link or image in a document.

    Attributes:
        url: The destination, an image's source included, as CommonMark reads it: escapes and character
            references decoded, then percent-encoded, so `[x](</a b>)` arrives as `/a%20b`. Never
            resolved against a path.
        line: The document line the link starts on, where it is used rather than where a reference-style
            link's definition sits.
    """

    url: str
    line: LineNumber

    def to_relative_path(self) -> PurePosixPath | None:
        """The relative path the destination spells, percent-decoded, or `None` when it spells none.

        The path is everything before the destination's `?query` or `#fragment`, decoded: `a%20b.md#usage` is
        `a b.md`. It is not normalised, so a `..` stays where it was written, and it is not resolved against any
        directory: which one it is read from is the caller's question.

        `None` for a destination that is no relative path: a URL with a scheme, such as `https:` or `mailto:`;
        one starting with `/`, as written or once decoded; and one with no path at all, such as a fragment-only
        `#usage` or an empty destination.
        """
        if _SCHEME.match(self.url) is not None or self.url.startswith('/'):
            return None
        path, _, _ = self.url.partition('#')
        path, _, _ = path.partition('?')
        if path == '':
            return None
        decoded = unquote(path)
        if decoded.startswith('/'):
            return None
        return PurePosixPath(decoded)
