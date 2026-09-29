"""Validated aspect filename stems."""

from dataclasses import dataclass
from typing import Self

from lorecraft.core.error import Error

from .name import AspectName, AspectNameError


class AspectFilenameError(Error):
    """An aspect filename is invalid."""

    filename: str


class InvalidAspectFilenameError(AspectFilenameError):
    """An aspect filename contains an invalid name."""

    def __init__(self, filename: str) -> None:
        self.filename = filename
        super().__init__(f'invalid name in aspect filename {filename!r}')


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

        Raises:
            InvalidAspectFilenameError: If the name is invalid; the lower-level validation
                error is chained as the cause.
        """
        try:
            parsed_name = AspectName.parse(filename)
        except AspectNameError as exc:
            raise InvalidAspectFilenameError(filename) from exc
        return cls(name=parsed_name)

    def __str__(self) -> str:
        return str(self.name)
