"""Where a node of a parse tree sits in its document: a one-based line number."""

from dataclasses import dataclass


class InvalidLineNumberError(ValueError):
    """A line number below 1 was given to ``LineNumber``.

    A ``ValueError`` rather than a ``lorecraft.core.error.Error``: no user input reaches a line number, so a
    rejected one is a defect in the code that produced it, and it must not be reported as invalid input.

    Attributes:
        value: The rejected number.
    """

    value: int

    def __init__(self, value: int) -> None:
        self.value = value
        super().__init__(f'line numbers are 1-based, got {value}')


@dataclass(frozen=True, slots=True)
class LineNumber:
    """A one-based line number in a document: 1 is the first line.

    Attributes:
        value: The line number, 1 or greater.
    """

    value: int

    def __post_init__(self) -> None:
        """Reject a number below 1, which names no line.

        Raises:
            InvalidLineNumberError: If ``value`` is below 1.
        """
        if self.value < 1:
            raise InvalidLineNumberError(self.value)

    def __str__(self) -> str:
        """The line number in decimal, as `path:line` output prints it."""
        return str(self.value)
