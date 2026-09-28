"""Validated names for documentation corpora."""

from dataclasses import dataclass
from string import ascii_lowercase, digits
from typing import Self

from lorecraft_core.error import Error


class CorpusNameError(Error):
    """A corpus name does not satisfy its format."""

    name: str


class EmptyCorpusNameError(CorpusNameError):
    """A corpus name is empty."""

    character: None

    def __init__(self) -> None:
        self.name = ''
        self.character = None
        super().__init__('corpus name cannot be empty')


class InvalidCorpusNameCharacterError(CorpusNameError):
    """A corpus name contains a character outside its format.

    Attributes:
        position: Zero-based position of the invalid character.
        character: The invalid character.
    """

    position: int
    character: str

    def __init__(self, name: str, position: int) -> None:
        self.name = name
        self.position = position
        self.character = name[position]
        if position == 0:
            message = (
                f'corpus name {name!r} must start with a lowercase ASCII letter or underscore, not {self.character!r}'
            )
        else:
            message = f'invalid character {self.character!r} in corpus name {name!r}'
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class CorpusName:
    """A validated corpus directory name beneath docs/.

    A valid name matches ``[a-z_][a-z0-9_]*``:

    - Is not empty.
    - Starts with a lowercase ASCII letter or underscore.
    - Continues with only lowercase ASCII letters, digits or underscores.

    Parsing preserves the spelling. The directory need not exist.

    Attributes:
        value: The validated directory name, exactly as supplied.
    """

    value: str

    @classmethod
    def parse(cls, raw: str) -> Self:
        """Return a validated corpus name.

        Raises:
            CorpusNameError: If the name is not lowercase snake case.
        """
        return cls(raw)

    def __post_init__(self) -> None:
        """Keep direct construction from bypassing the name invariant.

        Raises:
            CorpusNameError: If the name is not lowercase snake case.
        """
        if not self.value:
            raise EmptyCorpusNameError()

        first = self.value[0]
        if first not in ascii_lowercase and first != '_':
            raise InvalidCorpusNameCharacterError(self.value, 0)

        for position, character in enumerate(self.value[1:], start=1):
            if character not in ascii_lowercase and character not in digits and character != '_':
                raise InvalidCorpusNameCharacterError(self.value, position)

    def __str__(self) -> str:
        return self.value
