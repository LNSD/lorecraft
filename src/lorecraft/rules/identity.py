"""The identity values of a rule: its release, name, group, code and level, and the upstream names it answers to.

A `Release`, a `RuleName`, a `RuleGroupPrefix`, a `LinterName` and an `UpstreamCode` are value objects, which
cannot know whether their caller wrote a literal or parsed a file or a command line, so their format raises an
`Error` variant. A `RuleGroup`, a `RuleCode` and an `AliasCode` are records built from those values. Two of their
fields are plain values with a bound: a group's title and a code's number. No file and no command line supplies
either, since a user names a group by its prefix and a rule by its code, so one out of bounds is a defect in the
package, rejected with a `ValueError` rather than an `Error` that the command line would report as the user's
fault.
"""

from dataclasses import dataclass
from enum import StrEnum
from string import ascii_lowercase, ascii_uppercase, digits
from typing import ClassVar, Final, Self

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


class EmptyRuleGroupPrefixError(Error):
    """A rule group's prefix is empty."""

    def __init__(self) -> None:
        super().__init__('rule group prefix cannot be empty')


class InvalidRuleGroupPrefixCharacterError(Error):
    """A rule group's prefix holds a character other than an uppercase ASCII letter.

    Attributes:
        value: The rejected prefix.
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
        super().__init__(f'invalid character {self.character!r} in rule group prefix {value!r}')


class ReservedRuleGroupPrefixError(Error):
    """A rule group's prefix is `ALL`, the selector for every rule, so selecting the group would select them all.

    Attributes:
        value: The rejected prefix.
    """

    value: str

    def __init__(self, value: str) -> None:
        self.value = value
        super().__init__(f'rule group prefix {value!r} is reserved: it selects every rule')


@dataclass(frozen=True, slots=True)
class RuleGroupPrefix:
    """A rule group's prefix, which starts the code of every rule in the group, such as `OUT`.

    A valid prefix:

    - Is not empty.
    - Holds only uppercase ASCII letters.
    - Is not `ALL`, the selector for every rule.

    Parsing preserves the spelling.

    Attributes:
        value: The prefix, exactly as supplied.
    """

    value: str

    @classmethod
    def parse(cls, raw: str) -> Self:
        """Return a validated prefix.

        Args:
            raw: Candidate prefix, such as `OUT`.

        Raises:
            EmptyRuleGroupPrefixError: If it is empty.
            InvalidRuleGroupPrefixCharacterError: If it holds a character other than an uppercase ASCII letter.
            ReservedRuleGroupPrefixError: If it is `ALL`, the selector for every rule.
        """
        return cls(raw)

    def __post_init__(self) -> None:
        """Keep direct construction from bypassing the format.

        Raises:
            EmptyRuleGroupPrefixError: If it is empty.
            InvalidRuleGroupPrefixCharacterError: If it holds a character other than an uppercase ASCII letter.
            ReservedRuleGroupPrefixError: If it is `ALL`, the selector for every rule.
        """
        if not self.value:
            raise EmptyRuleGroupPrefixError()
        for position, character in enumerate(self.value):
            if character not in ascii_uppercase:
                raise InvalidRuleGroupPrefixCharacterError(self.value, position)
        if self.value == ALL_RULES_SELECTOR:
            raise ReservedRuleGroupPrefixError(self.value)

    def __str__(self) -> str:
        """The prefix exactly as supplied."""
        return self.value


class EmptyRuleGroupTitleError(ValueError):
    """A rule group's title is empty.

    Attributes:
        prefix: The prefix of the group with no title.
    """

    prefix: RuleGroupPrefix

    def __init__(self, prefix: RuleGroupPrefix) -> None:
        self.prefix = prefix
        super().__init__(f'rule group {str(prefix)!r} has an empty title')


@dataclass(frozen=True, slots=True)
class RuleGroup:
    """The rules one mechanism states, under one prefix and title, such as `OUT` for a structure's outline.

    Attributes:
        prefix: The prefix that starts the code of every rule in the group.
        title: What the group covers, for a reader; not empty.
    """

    prefix: RuleGroupPrefix
    title: str

    def __post_init__(self) -> None:
        """Reject an empty title.

        A title is text only the package writes, never input: no file or command line supplies one, so an empty
        title is a defect in the package that declares the group. A value object would raise an `Error`, which the
        command line reports as the user's fault, so the guard stays a `ValueError` (error-boundaries §1).

        Raises:
            EmptyRuleGroupTitleError: If the title is empty.
        """
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
        super().__init__(f'rule number {number} in group {str(group.prefix)!r} is outside 1 to 999')


@dataclass(frozen=True, slots=True)
class RuleCode:
    """A rule's code: its group and its number, printed as the prefix and three digits, such as `OUT002`.

    The prefix is the group's, so a code whose prefix disagrees with its group cannot be written.

    Attributes:
        group: The group the rule belongs to.
        number: The rule's number in its group, from 1 to 999.
    """

    DIGITS: ClassVar[int] = 3
    """How many digits end a printed code, after its group's prefix."""

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
        return f'{self.group.prefix}{self.number:0{self.DIGITS}d}'


ENGINE_GROUP: Final[RuleGroup] = RuleGroup(RuleGroupPrefix('LC'), 'Engine conditions')
"""The group reserved for engine conditions: only an `EngineCode` is in it, and the registry rejects, as the package
loads, a rule or a removed rule with a code in it."""


@dataclass(frozen=True, slots=True)
class EngineCode:
    """An engine condition's code: a number in the engine's group, printed as `LC` and three digits, such as `LC001`.

    It has no group to choose, so a condition's code can only be in the engine's group, and a code of any other
    group is a type error where a condition declares it.

    Attributes:
        number: The condition's number in the engine's group, from 1 to 999.
    """

    number: int

    def __post_init__(self) -> None:
        """Reject a number that would not print as three digits.

        Raises:
            RuleNumberOutOfRangeError: If the number is outside 1 to 999.
        """
        if not 1 <= self.number <= 999:
            raise RuleNumberOutOfRangeError(ENGINE_GROUP, self.number)

    @property
    def group(self) -> RuleGroup:
        """The engine's group, always."""
        return ENGINE_GROUP

    def __str__(self) -> str:
        """The code as output prints it: the engine's prefix, then the number zero-padded to three digits."""
        return f'{ENGINE_GROUP.prefix}{self.number:03d}'


class EmptyLinterNameError(Error):
    """An upstream linter's name is empty."""

    def __init__(self) -> None:
        super().__init__('linter name cannot be empty')


@dataclass(frozen=True, slots=True)
class LinterName:
    """The name of an upstream linter whose codes a rule answers to, such as `markdownlint`.

    A valid name is not empty. Parsing preserves the spelling.

    Attributes:
        value: The name, exactly as supplied.
    """

    value: str

    @classmethod
    def parse(cls, raw: str) -> Self:
        """Return a validated name.

        Args:
            raw: Candidate name, such as `markdownlint`.

        Raises:
            EmptyLinterNameError: If it is empty.
        """
        return cls(raw)

    def __post_init__(self) -> None:
        """Keep direct construction from bypassing the format.

        Raises:
            EmptyLinterNameError: If it is empty.
        """
        if not self.value:
            raise EmptyLinterNameError()

    def __str__(self) -> str:
        """The name exactly as supplied."""
        return self.value


class EmptyUpstreamCodeError(Error):
    """An upstream linter's code is empty."""

    def __init__(self) -> None:
        super().__init__('upstream code cannot be empty')


class InvalidUpstreamCodeCharacterError(Error):
    """An upstream linter's code holds whitespace, so it cannot be typed as one word.

    Attributes:
        value: The rejected code.
        position: Zero-based position of the first whitespace character.
        character: The whitespace character.
    """

    value: str
    position: int
    character: str

    def __init__(self, value: str, position: int) -> None:
        self.value = value
        self.position = position
        self.character = value[position]
        super().__init__(f'invalid character {self.character!r} in upstream code {value!r}')


@dataclass(frozen=True, slots=True)
class UpstreamCode:
    """An upstream linter's code, as the linter prints it, such as markdownlint's `MD040`.

    A valid code:

    - Is not empty.
    - Holds no whitespace character, so a user types it as one word.

    Parsing preserves the spelling.

    Attributes:
        value: The code, exactly as supplied.
    """

    value: str

    @classmethod
    def parse(cls, raw: str) -> Self:
        """Return a validated code.

        Args:
            raw: Candidate code, such as `MD040`.

        Raises:
            EmptyUpstreamCodeError: If it is empty.
            InvalidUpstreamCodeCharacterError: If it holds a whitespace character.
        """
        return cls(raw)

    def __post_init__(self) -> None:
        """Keep direct construction from bypassing the format.

        Raises:
            EmptyUpstreamCodeError: If it is empty.
            InvalidUpstreamCodeCharacterError: If it holds a whitespace character.
        """
        if not self.value:
            raise EmptyUpstreamCodeError()
        for position, character in enumerate(self.value):
            if character.isspace():
                raise InvalidUpstreamCodeCharacterError(self.value, position)

    def __str__(self) -> str:
        """The code exactly as supplied."""
        return self.value


@dataclass(frozen=True, slots=True)
class AliasCode:
    """An upstream linter's code for a rule Lorecraft absorbed, such as markdownlint's `MD040`.

    A rule's code is always Lorecraft's; an alias code only points to it.

    Attributes:
        linter: The upstream linter's name, such as `markdownlint`.
        code: The upstream code, as the linter prints it.
    """

    linter: LinterName
    code: UpstreamCode

    def __str__(self) -> str:
        """The upstream code alone, as a user types it to look the rule up."""
        return str(self.code)


class Severity(StrEnum):
    """How a diagnostic is reported; the value is the word the output spells it with.

    A severity is not a `Level`: a rule at `allow` does not run, so it reports nothing, and a diagnostic carries one
    of two severities where a level has three values. A rule's severity follows from its level; an engine
    condition fixes its own.
    """

    ERROR = 'error'
    """The diagnostic fails the run."""
    WARNING = 'warning'
    """The diagnostic is reported, and the run still passes."""
