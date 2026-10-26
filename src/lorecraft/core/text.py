"""Text values shared by every layer."""

from dataclasses import dataclass
from typing import Self

from .error import Error


class EmptyStrError(Error):
    """A string that must not be empty is empty.

    Attributes:
        value: The rejected empty string.
    """

    value: str

    def __init__(self, value: str) -> None:
        self.value = value
        super().__init__('string must not be empty')


@dataclass(frozen=True, slots=True, order=True)
class NonEmptyStr:
    """A string containing at least one character."""

    value: str

    def __post_init__(self) -> None:
        """Refuse an empty string.

        Raises:
            EmptyStrError: If `value` is empty.
        """
        if not self.value:
            raise EmptyStrError(self.value)

    @classmethod
    def parse(cls, raw: str) -> Self:
        """Build a non-empty string from text.

        Args:
            raw: The string to validate.

        Raises:
            EmptyStrError: If `raw` is empty.
        """
        return cls(raw)

    def __str__(self) -> str:
        """The contained string."""
        return self.value
