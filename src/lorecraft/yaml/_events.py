"""The seam over ruamel.yaml's errors: each is checked once here and read as a value of this package's own.

ruamel.yaml types an error's texts and marks loosely, as optional or `Any`. `parse_failure` and `code_point` convert
the library's errors, so the reader builds its problems from checked values.
"""

from dataclasses import dataclass

from ruamel.yaml.error import MarkedYAMLError, StreamMark
from ruamel.yaml.reader import ReaderError


@dataclass(frozen=True, slots=True)
class ParseFailure:
    """What ruamel.yaml's parser or scanner reported when the text is not valid YAML.

    Attributes:
        problem: What went wrong; empty where the library gave none.
        context: What it was reading; empty where the library gave none.
        problem_mark: Where it went wrong, or `None`.
        context_mark: Where the context starts, or `None`.
    """

    problem: str
    context: str
    problem_mark: StreamMark | None
    context_mark: StreamMark | None


def parse_failure(error: MarkedYAMLError) -> ParseFailure:
    """The report of a failed read, checked.

    Args:
        error: The library's error.
    """
    return ParseFailure(error.problem or '', error.context or '', error.problem_mark, error.context_mark)


def code_point(error: ReaderError) -> int:
    """The code point of the character the reader refused.

    Args:
        error: The reader's error, whose character is a code point, or a one-character text.
    """
    character = error.character
    return character if isinstance(character, int) else ord(character)
