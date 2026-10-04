"""Where a node of a parse tree sits in its document: a one-based line number."""

from dataclasses import dataclass
from typing import Self

from lorecraft.core.num import NonZeroUnsignedInt


@dataclass(frozen=True, slots=True)
class LineNumber:
    """A one-based line number in a document: 1 is the first line.

    Its own type rather than a bare `NonZeroUnsignedInt`, so a line number is never taken for another count.

    Attributes:
        value: The line number, 1 or greater.
    """

    value: NonZeroUnsignedInt

    @classmethod
    def parse(cls, raw: int) -> Self:
        """Return the line number `raw` names.

        Args:
            raw: Candidate line number, 1 for the first line.

        Raises:
            NonPositiveIntError: If the number is below 1, which names no line.
        """
        return cls(NonZeroUnsignedInt.parse(raw))

    @property
    def number(self) -> int:
        """The line number as a plain integer, for arithmetic, ordering and JSON output."""
        return self.value.value

    def __str__(self) -> str:
        """The line number in decimal, as `path:line` output prints it."""
        return str(self.value)
