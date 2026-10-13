"""The link nodes of a document's parse tree: every link and image the document's text holds, in document order.

A link's destination is kept as the parser reads it, never resolved: what it may point at is a check's question,
not the parser's. Which text is a link the Markdown parser decides (see `markdown`): a `[text](url)` inside
inline code or a code block is code, not a link, and a reference-style `[text][label]` is a link at the place it
is used, with the destination its definition gives.

What a destination is, though, is the parse tree's to tell: `Link.to_destination` is the one place a destination is
percent-decoded and classified, so every check reads the same answer and none of them matches on the raw `url`. The
destination is one of `ExternalDestination`, `AbsoluteDestination`, `FragmentDestination` or
`RelativeDestination`, and a relative one carries its path as a `NormalisedLinkPath`, with its `.` and `..`
components resolved lexically.
"""

import posixpath
import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Final, Self
from urllib.parse import unquote

from .position import LineNumber

_SCHEME: Final[re.Pattern[str]] = re.compile(r'[A-Za-z][A-Za-z0-9+.-]*:')
"""The scheme a URL starts with, such as `https:` or `mailto:`, as RFC 3986 spells one."""


@dataclass(frozen=True, slots=True)
class NormalisedLinkPath:
    """The relative path a link spells, percent-decoded and normalised lexically.

    A `.` component is dropped, and a `..` cancels the component before it as written, never as a symlink there
    would resolve: `references/./a.md` is `references/a.md`, `references/..` is `.`, and `../a.md` keeps its `..`,
    which is then the first component, the only place one can be left.

    `parse` is the only constructor: the path is normalised there, so a value built directly from a path that was
    not normalised would break the invariant.

    Attributes:
        path: The normalised path.
    """

    path: PurePosixPath

    @classmethod
    def parse(cls, decoded: str) -> Self:
        """Normalise a relative path that is already percent-decoded, as written and never resolved.

        Args:
            decoded: The path as the destination spells it, after percent-decoding.
        """
        return cls(path=PurePosixPath(posixpath.normpath(decoded)))

    def __str__(self) -> str:
        """The normalised path as text."""
        return str(self.path)


@dataclass(frozen=True, slots=True)
class ExternalDestination:
    """A destination with a URL scheme, such as `https://example.com` or `mailto:a@b.c`."""


@dataclass(frozen=True, slots=True)
class AbsoluteDestination:
    """A destination whose path starts with `/`, as written or once percent-decoded."""


@dataclass(frozen=True, slots=True)
class FragmentDestination:
    """A destination with no path: a fragment-only `#usage`, a bare `#`, a query alone or an empty destination.

    Attributes:
        fragment: What follows the `#`, still percent-encoded. Empty for a bare `#`, an empty destination and a
            query alone.
    """

    fragment: str


@dataclass(frozen=True, slots=True)
class RelativeDestination:
    """A destination that spells a relative path, whatever `?query` or `#fragment` follows it.

    Attributes:
        path: The path, percent-decoded and normalised.
    """

    path: NormalisedLinkPath


type LinkDestination = ExternalDestination | AbsoluteDestination | FragmentDestination | RelativeDestination
"""What a link's destination is: the closed set a check matches on."""


def _decoded_path(url: str) -> str:
    """The path of a destination, percent-decoded: everything before its `?query` or `#fragment`.

    Args:
        url: The destination as the Markdown parser encodes it.
    """
    path, _, _ = url.partition('#')
    path, _, _ = path.partition('?')
    return unquote(path)


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

    def to_destination(self) -> LinkDestination:
        """What the destination is: external, absolute, fragment-only or relative.

        The path is percent-decoded before it is classified, so `%2Fetc/x.md` is absolute. The scheme is read as
        written, since a decoded `a%3Ab.md` is the file `a:b.md`, not a URL.
        """
        if _SCHEME.match(self.url) is not None:
            return ExternalDestination()
        decoded = _decoded_path(self.url)
        if decoded.startswith('/'):
            return AbsoluteDestination()
        if decoded == '':
            # Only a destination that starts with `#` names a fragment; a query alone, `?a=b#c` included, names none.
            if self.url.startswith('#'):
                return FragmentDestination(fragment=self.url.removeprefix('#'))
            return FragmentDestination(fragment='')
        return RelativeDestination(path=NormalisedLinkPath.parse(decoded))
