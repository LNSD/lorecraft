"""Validated aspect filename stems."""

from dataclasses import dataclass
from typing import Self

from .name import AspectName


@dataclass(frozen=True, slots=True)
class AspectFilename:
    """A validated filename stem.

    Parsing ``python-errors-handling`` keeps that entire name; which namespace governs it is decided
    above, by the workspace model, so the filename carries no namespace of its own.

    Attributes:
        name: The entire filename stem without its extension.
    """

    name: AspectName

    @classmethod
    def parse(cls, filename: str) -> Self:
        """Parse the entire filename stem as the name.

        Args:
            filename: Document filename without its extension; kept whole, hyphens and all.

        Raises:
            EmptyAspectNameError: If the stem is empty.
            InvalidAspectNameCharacterError: If a character of the stem is not lowercase with valid separators.
        """
        # The stem is the whole name, so a failure is the name's own and passes through: a wrapper here would
        # hold nothing the name's error does not.
        return cls(name=AspectName.parse(filename))

    def __str__(self) -> str:
        """The filename stem, without its extension."""
        return str(self.name)
