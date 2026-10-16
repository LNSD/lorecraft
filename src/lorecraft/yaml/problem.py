"""What stops a YAML text from being read, as values that carry the facts a caller words a problem from.

A text that cannot be read is one problem, the first the text writes, in one of four kinds. No kind holds a type of the
YAML library, so a package above this one words each from the facts alone: the character a text is not allowed, the
error a parser reported with where it reported it, the construct the subset leaves out, or the depth the text nests
past.
"""

from dataclasses import dataclass
from typing import Final

from .tree import YamlPosition

LINE_SEPARATORS: Final[str] = '\x85\u2028\u2029'
"""The characters other YAML grammars end a line at, which `core/lines.py` does not: U+0085, U+2028 and U+2029."""


@dataclass(frozen=True, slots=True)
class ControlCharacterProblem:
    """The text holds a character YAML does not allow, such as a control character.

    Attributes:
        code: The character's code point.
        index: Where it is in the text, counted in characters from 0.
    """

    code: int
    index: int


@dataclass(frozen=True, slots=True)
class SyntaxErrorProblem:
    """The text is not valid YAML, as the parser or the scanner reported it.

    Attributes:
        problem: What the parser found wrong, in its own words, or an empty text when it gave none.
        context: What it was reading, in its own words, or an empty text when it gave none.
        position: Where it found the problem, or `None` when it gave no mark.
        context_position: Where what it was reading began, or `None` when it gave no mark.
    """

    problem: str
    context: str
    position: YamlPosition | None
    context_position: YamlPosition | None


@dataclass(frozen=True, slots=True)
class Directive:
    """A directive, a `%` line, is written.

    Attributes:
        name: The `%` and the name that follows it.
    """

    name: str


@dataclass(frozen=True, slots=True)
class DocumentMarker:
    """A `---` or `...` marker is written, though the text is the body of one document.

    Attributes:
        marker: The three characters of the marker.
    """

    marker: str


@dataclass(frozen=True, slots=True)
class Alias:
    """A value is an alias.

    Attributes:
        anchor: The anchor's name, without the `*`.
    """

    anchor: str


@dataclass(frozen=True, slots=True)
class Anchor:
    """A value carries an anchor.

    Attributes:
        anchor: The anchor's name, without the `&`.
    """

    anchor: str


@dataclass(frozen=True, slots=True)
class Tag:
    """A value carries a tag, the non-specific `!` included, or a tag the scanner cannot read.

    Attributes:
        tag: The tag as the text writes it.
    """

    tag: str


@dataclass(frozen=True, slots=True)
class MergeKey:
    """A mapping writes the plain key `<<`, which YAML 1.1 reads as a merge."""


@dataclass(frozen=True, slots=True)
class CollectionKey:
    """A mapping's key is a collection, not a string."""


@dataclass(frozen=True, slots=True)
class NonStringKey:
    """A mapping's key is a scalar that decodes to null, a boolean or a number, not a string.

    Attributes:
        key: The key as written, which is empty for a key written as nothing at all.
    """

    key: str


@dataclass(frozen=True, slots=True)
class FlowCollectionRoot:
    """The whole text is a flow collection, not a block mapping."""


@dataclass(frozen=True, slots=True)
class CollectionInFlow:
    """A flow collection holds a collection."""


@dataclass(frozen=True, slots=True)
class NestedBlockSequence:
    """A block sequence holds a block sequence as an item."""


@dataclass(frozen=True, slots=True)
class EscapeBeyondUnicode:
    """A double-quoted escape names a code point above `U+10FFFF`, which no character has."""


@dataclass(frozen=True, slots=True)
class ExplicitKey:
    """A mapping key is written with the explicit `?` indicator."""


@dataclass(frozen=True, slots=True)
class EmptyKey:
    """A mapping key is written as nothing at all."""


@dataclass(frozen=True, slots=True)
class IndentationIndicator:
    """A block scalar writes an indentation indicator."""


@dataclass(frozen=True, slots=True)
class SpreadFlowCollection:
    """A flow collection is spread over several lines."""


@dataclass(frozen=True, slots=True)
class LineSeparator:
    """The text holds U+0085, U+2028 or U+2029 outside a quoted scalar, where it is not a line break.

    Attributes:
        character: The separator.
    """

    character: str


type RefusedConstruct = (
    Directive
    | DocumentMarker
    | Alias
    | Anchor
    | Tag
    | MergeKey
    | CollectionKey
    | NonStringKey
    | FlowCollectionRoot
    | CollectionInFlow
    | NestedBlockSequence
    | EscapeBeyondUnicode
    | ExplicitKey
    | EmptyKey
    | IndentationIndicator
    | SpreadFlowCollection
    | LineSeparator
)
"""A construct the subset leaves out, as the facts a package above words a problem from."""


@dataclass(frozen=True, slots=True)
class RefusedConstructProblem:
    """The text writes a construct the subset leaves out, such as an anchor, a tag or a merge key.

    Attributes:
        construct: Which construct it is.
        position: Where the construct is written.
    """

    construct: RefusedConstruct
    position: YamlPosition


@dataclass(frozen=True, slots=True)
class NestingTooDeepProblem:
    """The text nests collections deeper than the interpreter's stack reads, so no position is known."""


type YamlProblem = ControlCharacterProblem | SyntaxErrorProblem | RefusedConstructProblem | NestingTooDeepProblem
"""Why a text could not be read: the first problem it writes."""
