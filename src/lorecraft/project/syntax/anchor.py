"""A heading's anchor: the name a fragment-only link such as ``#usage`` points at.

An anchor is derived here as GitHub derives it, not with wenmode's own heading ids, which collapse whitespace and
number repeats differently: a link that works where the document is read must pass the check. A link's fragment
is a different thing, raw text the author typed, and the only way to compare one with an anchor is through
``Anchor.from_fragment``, which applies the one normalisation GitHub applies before it looks the fragment up.
"""

import unicodedata
from dataclasses import dataclass
from typing import Final, Self
from urllib.parse import unquote

_ANCHOR_CATEGORIES: Final[frozenset[str]] = frozenset(
    {'Lu', 'Ll', 'Lt', 'Lm', 'Lo', 'Mn', 'Mc', 'Me', 'Nd', 'Nl', 'Pc'}
)
"""The Unicode categories an anchor keeps: letters, marks, decimal and letter numbers, connectors."""


class InvalidAnchorError(ValueError):
    """A value holding a character no anchor holds was given to ``Anchor``.

    A ``ValueError`` rather than a ``lorecraft.core.error.Error``: no user input reaches the constructor, since a
    heading's text and a link's fragment both go through a named conversion that only builds valid anchors, so a
    rejected one is a defect in the code that produced it, and it must not be reported as invalid input.

    Attributes:
        value: The rejected value.
        position: Where its first character outside the format sits, zero-based.
        character: That character.
    """

    value: str
    position: int
    character: str

    def __init__(self, value: str, position: int) -> None:
        self.value = value
        self.position = position
        self.character = value[position]
        super().__init__(f'invalid character {self.character!r} at {position} in anchor {value!r}')


@dataclass(frozen=True, slots=True)
class Anchor:
    """A heading anchor as GitHub derives it, the name a ``#fragment`` link resolves to.

    Every character of a valid anchor is lowercase and is either a hyphen-minus or one whose Unicode category is
    a letter, a mark, a decimal or letter number, or connector punctuation such as ``_``. So a letter in any
    script is held with its combining marks, as in ``हिन्दी`` or a decomposed ``é``, while a space, punctuation, a
    symbol, an en dash and a number such as ``½`` are not. The value is not Unicode-normalized, and may be empty:
    a heading of nothing but punctuation has the empty anchor.

    Attributes:
        value: The anchor, without the leading ``#``.
    """

    value: str

    def __post_init__(self) -> None:
        """Reject a value holding a character outside the format.

        Raises:
            InvalidAnchorError: If a character of ``value`` is not one an anchor holds.
        """
        for position, character in enumerate(self.value):
            if not _is_anchor_character(character):
                raise InvalidAnchorError(self.value, position)

    @classmethod
    def from_heading(cls, text: str) -> Self:
        """The anchor GitHub derives from a heading's rendered text, before a repeated heading is numbered.

        The rule is github-slugger's, which GitHub uses: lowercase the text, turn each space into a hyphen, and
        drop every character an anchor does not hold. Spaces are not collapsed, so `C++ & Rust` is `c--rust`:
        the dropped `&` leaves the spaces on either side of it.

        Args:
            text: The heading's rendered text: what it shows, not its Markdown source.
        """
        kept: list[str] = []
        for character in text.lower().replace(' ', '-'):
            if _is_anchor_character(character):
                kept.append(character)
        return cls(''.join(kept))

    def numbered(self, n: int) -> Self:
        """The anchor a repeat of this one's heading takes: ``foo`` numbered 1 is ``foo-1``.

        Args:
            n: Which repeat, 1 for the first heading after the one holding the bare anchor.
        """
        return type(self)(f'{self.value}-{n}')

    @classmethod
    def from_fragment(cls, fragment: str) -> Self | None:
        """The anchor a link's fragment resolves to, or ``None`` when no heading can have it.

        GitHub resolves a fragment regardless of case, and the parser percent-encodes a link's destination, so
        the fragment is percent-decoded and lowercased: ``Usage`` and ``Stra%C3%9Fe`` give ``usage`` and
        ``straße``. A fragment that is still no anchor after that, such as one holding a space or a ``!``, is
        ``None`` rather than an error, since a link naming no heading is an ordinary finding, not invalid input.

        Args:
            fragment: The link's fragment, without the leading ``#``.
        """
        candidate = unquote(fragment).lower()
        for character in candidate:
            if not _is_anchor_character(character):
                return None
        return cls(candidate)

    def __str__(self) -> str:
        """The anchor without the leading `#`, as a link fragment is compared with it."""
        return self.value


def _is_anchor_character(character: str) -> bool:
    """Whether an anchor holds the character: the one statement of the format `Anchor` documents.

    Args:
        character: A single character, tested on its own.
    """
    # Lowercase is tested one character at a time rather than as `value == value.lower()`: the only rule of
    # `str.lower` that depends on its neighbours turns a capital sigma final, and a capital sigma fails here on its
    # own. Lowering a character never yields one that a second lowering changes, so a lowered heading or fragment
    # loses nothing to this test: `İ` lowers to `i` plus a combining dot, both held.
    if character.lower() != character:
        return False
    return character == '-' or unicodedata.category(character) in _ANCHOR_CATEGORIES
