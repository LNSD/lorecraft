"""Validated names for document specification aspects."""

from dataclasses import dataclass
from string import ascii_lowercase, digits
from typing import Self

from lorecraft.core.error import Error


class EmptyAspectNameError(Error):
    """An aspect name is empty."""

    def __init__(self) -> None:
        super().__init__('aspect name cannot be empty')


class InvalidAspectNameCharacterError(Error):
    """An aspect name contains a character outside its format.

    Attributes:
        name: The rejected aspect name.
        position: Zero-based position of the invalid character.
        character: The invalid character.
    """

    name: str
    position: int
    character: str

    def __init__(self, name: str, position: int) -> None:
        self.name = name
        self.position = position
        self.character = name[position]
        super().__init__(f'invalid character {self.character!r} in aspect name {name!r}')


@dataclass(frozen=True, slots=True)
class AspectName:
    """A validated lowercase aspect name with hyphen or underscore separators.

    A valid name matches ``[a-z][a-z0-9]*(?:[-_][a-z0-9]+)*``:

    - Is not empty.
    - Starts with a lowercase ASCII letter.
    - Contains only lowercase ASCII letters or digits, with single hyphens or underscores
      between non-empty segments.

    Parsing preserves the spelling.

    Attributes:
        value: The validated aspect name, exactly as supplied.
    """

    value: str

    @classmethod
    def parse(cls, raw: str) -> Self:
        """Return a validated aspect name.

        Raises:
            EmptyAspectNameError: If the name is empty.
            InvalidAspectNameCharacterError: If a character is not lowercase with valid separators.
        """
        return cls(raw)

    def __post_init__(self) -> None:
        """Keep direct construction from bypassing the name invariant.

        Raises:
            EmptyAspectNameError: If the name is empty.
            InvalidAspectNameCharacterError: If a character is not lowercase with valid separators.
        """
        _validate_aspect_name(self.value)

    def __str__(self) -> str:
        return self.value


def _validate_aspect_name(name: str) -> None:
    if not name:
        raise EmptyAspectNameError()
    if name[0] not in ascii_lowercase:
        raise InvalidAspectNameCharacterError(name, 0)

    previous_was_separator = False
    for position, character in enumerate(name[1:], start=1):
        if character in '-_':
            if previous_was_separator:
                raise InvalidAspectNameCharacterError(name, position)
            previous_was_separator = True
        elif character in ascii_lowercase or character in digits:
            previous_was_separator = False
        else:
            raise InvalidAspectNameCharacterError(name, position)

    if previous_was_separator:
        raise InvalidAspectNameCharacterError(name, len(name) - 1)
