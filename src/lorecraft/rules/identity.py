"""The identity values of the rules package: a release, a rule's name and the level it is configured at."""

from dataclasses import dataclass
from enum import StrEnum
from string import ascii_lowercase, digits
from typing import Final, Self

from lorecraft.core.error import Error


class MalformedReleaseError(Error):
    """A release is not three runs of ASCII digits joined by dots.

    Attributes:
        value: The rejected release.
    """

    value: str

    def __init__(self, value: str) -> None:
        self.value = value
        super().__init__(f'release {value!r} is not in the form MAJOR.MINOR.PATCH')


class LeadingZeroReleaseError(Error):
    """A component of a release starts with a zero and has more digits after it.

    Attributes:
        value: The rejected release.
        component: The component with the leading zero.
    """

    value: str
    component: str

    def __init__(self, value: str, component: str) -> None:
        self.value = value
        self.component = component
        super().__init__(f'release {value!r} has a leading zero in {component!r}')


@dataclass(frozen=True, slots=True)
class Release:
    """A release of the package, in the form `MAJOR.MINOR.PATCH`, such as `0.3.0`.

    A valid release:

    - Is three components joined by dots.
    - Holds only ASCII digits in each component, so no `v` prefix and no pre-release or build suffix.
    - Has no leading zero in a component, though a component may be `0` itself.

    Parsing preserves the spelling.

    Attributes:
        value: The release, exactly as supplied.
    """

    value: str

    @classmethod
    def parse(cls, raw: str) -> Self:
        """Return a validated release.

        Args:
            raw: Candidate release, such as `0.3.0`.

        Raises:
            MalformedReleaseError: If it is not three runs of ASCII digits joined by dots.
            LeadingZeroReleaseError: If a component has a leading zero.
        """
        return cls(raw)

    def __post_init__(self) -> None:
        """Keep direct construction from bypassing the format.

        Raises:
            MalformedReleaseError: If it is not three runs of ASCII digits joined by dots.
            LeadingZeroReleaseError: If a component has a leading zero.
        """
        components = self.value.split('.')
        if len(components) != 3:
            raise MalformedReleaseError(self.value)
        for component in components:
            if not component or any(character not in digits for character in component):
                raise MalformedReleaseError(self.value)
        for component in components:
            if len(component) > 1 and component.startswith('0'):
                raise LeadingZeroReleaseError(self.value, component)

    def __str__(self) -> str:
        """The release exactly as supplied."""
        return self.value


class EmptyRuleNameError(Error):
    """A rule name is empty."""

    def __init__(self) -> None:
        super().__init__('rule name cannot be empty')


class InvalidRuleNameCharacterError(Error):
    """A rule name holds a character other than a lowercase ASCII letter, a digit or a hyphen.

    Attributes:
        value: The rejected name.
        position: Zero-based position of the first invalid character.
        character: The invalid character.
    """

    value: str
    position: int
    character: str

    def __init__(self, value: str, position: int) -> None:
        self.value = value
        self.position = position
        self.character = value[position]
        super().__init__(f'invalid character {self.character!r} in rule name {value!r}')


class LeadingHyphenRuleNameError(Error):
    """A rule name starts with a hyphen.

    Attributes:
        value: The rejected name.
    """

    value: str

    def __init__(self, value: str) -> None:
        self.value = value
        super().__init__(f'rule name {value!r} starts with a hyphen')


class TrailingHyphenRuleNameError(Error):
    """A rule name ends with a hyphen.

    Attributes:
        value: The rejected name.
    """

    value: str

    def __init__(self, value: str) -> None:
        self.value = value
        super().__init__(f'rule name {value!r} ends with a hyphen')


class DoubledHyphenRuleNameError(Error):
    """A rule name holds two hyphens in a row.

    Attributes:
        value: The rejected name.
        position: Zero-based position of the first of the two hyphens.
    """

    value: str
    position: int

    def __init__(self, value: str, position: int) -> None:
        self.value = value
        self.position = position
        super().__init__(f'rule name {value!r} has two hyphens in a row at position {position}')


@dataclass(frozen=True, slots=True)
class RuleName:
    """A rule's name, the kebab-case identity beside its code, such as `empty-section`.

    A valid name:

    - Is not empty.
    - Holds only lowercase ASCII letters, ASCII digits and hyphens.
    - Neither starts nor ends with a hyphen, and holds no two hyphens in a row, so it is one or more words
      joined by single hyphens.

    Parsing preserves the spelling.

    Attributes:
        value: The name, exactly as supplied.
    """

    value: str

    @classmethod
    def parse(cls, raw: str) -> Self:
        """Return a validated name.

        Args:
            raw: Candidate name, such as `empty-section`.

        Raises:
            EmptyRuleNameError: If it is empty.
            InvalidRuleNameCharacterError: If it holds a character other than a lowercase ASCII letter, a digit
                or a hyphen.
            LeadingHyphenRuleNameError: If it starts with a hyphen.
            TrailingHyphenRuleNameError: If it ends with a hyphen.
            DoubledHyphenRuleNameError: If it holds two hyphens in a row.
        """
        return cls(raw)

    def __post_init__(self) -> None:
        """Keep direct construction from bypassing the format.

        The characters are checked before the hyphens, so a name with both faults reports its invalid character.

        Raises:
            EmptyRuleNameError: If it is empty.
            InvalidRuleNameCharacterError: If it holds a character other than a lowercase ASCII letter, a digit
                or a hyphen.
            LeadingHyphenRuleNameError: If it starts with a hyphen.
            TrailingHyphenRuleNameError: If it ends with a hyphen.
            DoubledHyphenRuleNameError: If it holds two hyphens in a row.
        """
        if not self.value:
            raise EmptyRuleNameError()
        for position, character in enumerate(self.value):
            if character not in ascii_lowercase and character not in digits and character != '-':
                raise InvalidRuleNameCharacterError(self.value, position)
        if self.value.startswith('-'):
            raise LeadingHyphenRuleNameError(self.value)
        if self.value.endswith('-'):
            raise TrailingHyphenRuleNameError(self.value)
        doubled = self.value.find('--')
        if doubled != -1:
            raise DoubledHyphenRuleNameError(self.value, doubled)

    def __str__(self) -> str:
        """The name exactly as supplied."""
        return self.value


ALL_RULES_SELECTOR: Final[str] = 'ALL'
"""The selector for every rule, as ruff spells it, which no group may take as its prefix."""


class Level(StrEnum):
    """How a rule is configured; the value is the word a configuration spells it with."""

    ALLOW = 'allow'
    """The rule does not run."""
    WARN = 'warn'
    """An occurrence of the rule is reported as a warning."""
    DENY = 'deny'
    """An occurrence of the rule is reported as an error."""
