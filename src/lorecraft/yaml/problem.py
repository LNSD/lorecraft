"""What stops a YAML text from being read, as values that carry the facts a caller words a problem from.

A text that cannot be read is one problem, the first the text writes, in one of four kinds. No kind holds a type of the
YAML library, so a package above this one words each from the facts alone: the character a text is not allowed, the
error a parser reported with where it reported it, the construct the subset leaves out, or the depth the text nests
past.
"""

from dataclasses import dataclass
from typing import Final, get_args

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
class RefusedConstructProblem:
    """The text writes a construct the subset leaves out, such as an anchor, a tag or a merge key.

    Attributes:
        message: What was found, as a sentence that names the construct.
        help: What to do about it, or `None` where the message says all there is.
        position: Where the construct is written.
    """

    message: str
    help: str | None
    position: YamlPosition


@dataclass(frozen=True, slots=True)
class NestingTooDeepProblem:
    """The text nests collections deeper than the interpreter's stack reads, so no position is known."""


type YamlProblem = ControlCharacterProblem | SyntaxErrorProblem | RefusedConstructProblem | NestingTooDeepProblem
"""Why a text could not be read: the first problem it writes."""

YAML_PROBLEMS: Final = get_args(YamlProblem.__value__)
"""The classes of `YamlProblem`, for a caller that tells a problem from a value."""
