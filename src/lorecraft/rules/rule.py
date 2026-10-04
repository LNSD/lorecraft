"""How a rule is declared: its identity values.

A `Release` is a value object, which cannot know whether its caller joined a literal or parsed a file, so its
format raises an `Error` variant. A `RuleGroup`, a `RuleCode` and an `AliasCode` are records only the package's
own code builds, from literals in a rule's module, never from a file a command read. One that breaks its format
is therefore a defect in the package, and is rejected with a `ValueError` rather than an `Error` that the command
line would report as the user's fault.
"""

from dataclasses import dataclass
from enum import Enum
from string import ascii_uppercase, digits
from typing import Self

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


class InvalidRuleGroupPrefixError(ValueError):
    """A rule group's prefix is empty or holds a character other than an uppercase ASCII letter.

    Attributes:
        prefix: The rejected prefix.
    """

    prefix: str

    def __init__(self, prefix: str) -> None:
        self.prefix = prefix
        super().__init__(f'rule group prefix {prefix!r} must be one or more uppercase ASCII letters')


class EmptyRuleGroupTitleError(ValueError):
    """A rule group's title is empty.

    Attributes:
        prefix: The prefix of the group with no title.
    """

    prefix: str

    def __init__(self, prefix: str) -> None:
        self.prefix = prefix
        super().__init__(f'rule group {prefix!r} has an empty title')


@dataclass(frozen=True, slots=True)
class RuleGroup:
    """The rules one mechanism states, under one prefix and title, such as `OUT` for a structure's outline.

    Attributes:
        prefix: One or more uppercase ASCII letters, which start the code of every rule in the group.
        title: What the group covers, for a reader; not empty.
    """

    prefix: str
    title: str

    def __post_init__(self) -> None:
        """Reject a prefix outside its format and an empty title.

        Raises:
            InvalidRuleGroupPrefixError: If the prefix is empty or holds a character other than an uppercase
                ASCII letter.
            EmptyRuleGroupTitleError: If the title is empty.
        """
        if not self.prefix or any(character not in ascii_uppercase for character in self.prefix):
            raise InvalidRuleGroupPrefixError(self.prefix)
        if not self.title:
            raise EmptyRuleGroupTitleError(self.prefix)


class RuleNumberOutOfRangeError(ValueError):
    """A rule's number is outside 1 to 999, so it would not print as three digits.

    Attributes:
        group: The group of the code.
        number: The rejected number.
    """

    group: RuleGroup
    number: int

    def __init__(self, group: RuleGroup, number: int) -> None:
        self.group = group
        self.number = number
        super().__init__(f'rule number {number} in group {group.prefix!r} is outside 1 to 999')


@dataclass(frozen=True, slots=True)
class RuleCode:
    """A rule's code: its group and its number, printed as the prefix and three digits, such as `OUT002`.

    The prefix is the group's, so a code whose prefix disagrees with its group cannot be written.

    Attributes:
        group: The group the rule belongs to.
        number: The rule's number in its group, from 1 to 999.
    """

    group: RuleGroup
    number: int

    def __post_init__(self) -> None:
        """Reject a number that would not print as three digits.

        Raises:
            RuleNumberOutOfRangeError: If the number is outside 1 to 999.
        """
        if not 1 <= self.number <= 999:
            raise RuleNumberOutOfRangeError(self.group, self.number)

    def __str__(self) -> str:
        """The code as output prints it: the group's prefix, then the number zero-padded to three digits."""
        return f'{self.group.prefix}{self.number:03d}'


class EmptyAliasLinterError(ValueError):
    """An alias code names no upstream linter.

    Attributes:
        code: The upstream code of the alias.
    """

    code: str

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(f'alias code {code!r} names no linter')


class InvalidAliasCodeError(ValueError):
    """An alias code's upstream code is empty or holds whitespace, so it cannot be typed as one word.

    Attributes:
        linter: The upstream linter of the alias.
        code: The rejected code.
    """

    linter: str
    code: str

    def __init__(self, linter: str, code: str) -> None:
        self.linter = linter
        self.code = code
        super().__init__(f'alias code {code!r} of {linter!r} must be one or more characters without whitespace')


@dataclass(frozen=True, slots=True)
class AliasCode:
    """An upstream linter's code for a rule Lorecraft absorbed, such as markdownlint's `MD040`.

    A rule's code is always Lorecraft's; an alias code only points to it.

    Attributes:
        linter: The upstream linter's name, such as `markdownlint`; not empty.
        code: The upstream code, as the linter prints it; not empty, and without whitespace.
    """

    linter: str
    code: str

    def __post_init__(self) -> None:
        """Reject an alias with no linter, and an upstream code that is not one word.

        Raises:
            EmptyAliasLinterError: If the linter's name is empty.
            InvalidAliasCodeError: If the code is empty or holds whitespace.
        """
        if not self.linter:
            raise EmptyAliasLinterError(self.code)
        if not self.code or any(character.isspace() for character in self.code):
            raise InvalidAliasCodeError(self.linter, self.code)

    def __str__(self) -> str:
        """The upstream code alone, as a user types it to look the rule up."""
        return self.code


class Level(Enum):
    """How a rule is configured; the value is the word a configuration spells it with."""

    ALLOW = 'allow'
    """The rule does not run."""
    WARN = 'warn'
    """An occurrence of the rule is reported as a warning."""
    DENY = 'deny'
    """An occurrence of the rule is reported as an error."""
