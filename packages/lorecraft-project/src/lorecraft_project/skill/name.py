"""Validated skill names, as the Agent Skills specification defines them."""

from dataclasses import dataclass
from string import ascii_lowercase, digits
from typing import Final, Self

from lorecraft_core.error import Error

SKILL_NAME_MAX_LENGTH: Final[int] = 64


class SkillNameError(Error):
    """A skill name does not satisfy the Agent Skills specification.

    Attributes:
        name: The rejected name, exactly as supplied.
    """

    name: str


class EmptySkillNameError(SkillNameError):
    """A skill name is empty."""

    def __init__(self) -> None:
        self.name = ''
        super().__init__('skill name cannot be empty')


class SkillNameTooLongError(SkillNameError):
    """A skill name is longer than ``SKILL_NAME_MAX_LENGTH`` characters.

    Attributes:
        length: The rejected name's length in characters.
    """

    length: int

    def __init__(self, name: str) -> None:
        self.name = name
        self.length = len(name)
        super().__init__(
            f'skill name {name!r} is {self.length} characters long, over the limit of {SKILL_NAME_MAX_LENGTH}'
        )


class InvalidSkillNameCharacterError(SkillNameError):
    """A skill name contains a character outside its format, or a hyphen where no segment surrounds it.

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
        if self.character == '-':
            message = f'misplaced hyphen at position {position} in skill name {name!r}'
        else:
            message = f'invalid character {self.character!r} at position {position} in skill name {name!r}'
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class SkillName:
    """A validated skill name.

    A valid name matches ``^[a-z0-9]+(-[a-z0-9]+)*$``:

    - Is 1 to 64 characters long.
    - Contains only lowercase ASCII letters, digits and hyphens.
    - Neither starts nor ends with a hyphen, and never holds two hyphens in a row.

    Parsing preserves the spelling. The frontmatter ``name`` of a skill must equal its directory name; the
    check reports a mismatch.

    Attributes:
        value: The validated name, exactly as supplied.
    """

    value: str

    @classmethod
    def parse(cls, raw: str) -> Self:
        """Return a validated skill name.

        Raises:
            SkillNameError: If the name is empty, too long, or not lowercase kebab-case.
        """
        return cls(raw)

    def __post_init__(self) -> None:
        """Keep direct construction from bypassing the name invariant.

        Raises:
            SkillNameError: If the name is empty, too long, or not lowercase kebab-case.
        """
        _validate_skill_name(self.value)

    def __str__(self) -> str:
        return self.value


def _validate_skill_name(name: str) -> None:
    if not name:
        raise EmptySkillNameError()
    if len(name) > SKILL_NAME_MAX_LENGTH:
        raise SkillNameTooLongError(name)

    previous_was_hyphen = True  # a hyphen at position 0 is rejected like one after a hyphen
    for position, character in enumerate(name):
        if character == '-':
            if previous_was_hyphen:
                raise InvalidSkillNameCharacterError(name, position)
            previous_was_hyphen = True
        elif character in ascii_lowercase or character in digits:
            previous_was_hyphen = False
        else:
            raise InvalidSkillNameCharacterError(name, position)

    if previous_was_hyphen:
        raise InvalidSkillNameCharacterError(name, len(name) - 1)
