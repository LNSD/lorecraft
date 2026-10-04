"""How a rule is declared: its identity values, the rule class that declares it, and `@rule`.

A rule is one class. The class is the declaration and the check: its code, name, default level, the
release it is stable since and its documentation, as class attributes and the docstring, and the `check`
classmethod that judges its input. Each input kind has one base class deriving from `ContentRule` or
`LayoutRule`, whose abstract `check` fixes the input's type, so a rule picks its input by picking its base.
A retired rule is a `RemovedRule`, which is not a `Rule`, so it can never be built as one or reported.

`@rule` records each declaration as its module is imported. The registry walks a rules package, imports every
module in it but its unit tests, and keeps the declarations whose module lies in that package outside its unit
tests, so the rules a test declares never reach the package's own registry.

A `Release` and a `RuleName` are value objects, which cannot know whether their caller wrote a literal or parsed
a file or a command line, so their format raises an `Error` variant. A `RuleGroup`, a `RuleCode` and an
`AliasCode` are records only the package's own code builds, from literals in a rule's module, never from a file a
command read. One that breaks its format is therefore a defect in the package, and is rejected with a `ValueError`
rather than an `Error` that the command line would report as the user's fault.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from string import ascii_lowercase, ascii_uppercase, digits
from typing import ClassVar, Self

from lorecraft.core.error import Error
from lorecraft.core.path import RootRelativePath
from lorecraft.project.syntax import LineNumber

from .location import (
    EntryLabel,
    EntrySubdiagnostic,
    Here,
    Label,
    Primary,
    Subdiagnostic,
    WholeSubject,
)


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


@dataclass(frozen=True, slots=True, kw_only=True)
class Rule(ABC):
    """A rule, declared and checked by its class.

    An instance of a rule is one occurrence of it, at one place, which is why its `check` returns `tuple[Self, ...]`.

    A subclass declares the rule in its class attributes and its docstring, adds the data of its own condition
    and the context its diagnostic needs as fields, and renders every part of the diagnostic from those fields.
    It names no subject: the run that checked the subject locates it.

    A rule never derives from this class directly, but from its input's base, which derives from
    `ContentRule` or `LayoutRule` and declares the abstract `check` a rule implements.

    Attributes:
        spec: The specification file that states the rule, or None for a rule the package itself states.
        CODE: The rule's code, such as `OUT002`.
        NAME: The rule's kebab-case name, such as `empty-section`.
        LEVEL: The level the rule runs at when nothing configures it.
        SINCE: The release the rule is stable since.
        ALIASES: The upstream linters' codes the rule answers to; none, the default, for most rules.
    """

    CODE: ClassVar[RuleCode]
    NAME: ClassVar[RuleName]
    LEVEL: ClassVar[Level]
    SINCE: ClassVar[Release]
    ALIASES: ClassVar[tuple[AliasCode, ...]] = ()

    spec: RootRelativePath | None

    @abstractmethod
    def message(self) -> str:
        """What is wrong, rendered from the fields, the same template for every occurrence."""

    @abstractmethod
    def primary(self) -> Primary:
        """Where the diagnostic points first."""

    def labels(self) -> tuple[Label | EntryLabel, ...]:
        """The labelled locations of this occurrence; none, so the primary location is unlabelled."""
        return ()

    def children(self) -> tuple[Subdiagnostic | EntrySubdiagnostic, ...]:
        """The help and notes printed under the message; none."""
        return ()


@dataclass(frozen=True, slots=True, kw_only=True)
class ContentRule(Rule):
    """A rule of a subject with lines: a document, a skill or a skill resource.

    Its labels and sub-diagnostics may point at a line of the subject or elsewhere.

    Attributes:
        line: The line the occurrence is reported at.
    """

    line: LineNumber

    def primary(self) -> Here:
        """The occurrence's line."""
        return Here(self.line)

    def labels(self) -> tuple[Label, ...]:
        """The labelled locations of this occurrence; none, so the occurrence's line is unlabelled."""
        return ()

    def children(self) -> tuple[Subdiagnostic, ...]:
        """The help and notes printed under the message; none."""
        return ()


@dataclass(frozen=True, slots=True, kw_only=True)
class LayoutRule(Rule):
    """A rule of a layout entry, which has no lines, so it carries none.

    Its labels and sub-diagnostics can only point at another file.
    """

    def primary(self) -> WholeSubject:
        """The layout entry itself."""
        return WholeSubject()

    def labels(self) -> tuple[EntryLabel, ...]:
        """The labelled locations of this occurrence; none, so the entry is unlabelled."""
        return ()

    def children(self) -> tuple[EntrySubdiagnostic, ...]:
        """The help and notes printed under the message; none."""
        return ()


class RemovedRule:
    """A retired rule: its code stays taken, and a configuration that names it learns what replaced it.

    A subclass declares the retired rule in its class attributes, and its docstring says why it was retired. It
    is not a `Rule`, so it can never be built as one or reported.

    Attributes:
        CODE: The code the rule had, never free to reuse.
        NAME: The name the rule had.
        REMOVED_IN: The release that removed the rule.
        REPLACED_BY: The code of the rule that replaced it, or None when nothing did.
    """

    CODE: ClassVar[RuleCode]
    NAME: ClassVar[RuleName]
    REMOVED_IN: ClassVar[Release]
    REPLACED_BY: ClassVar[RuleCode | None]


# What `@rule` registers: a rule in service, as its class, or a retired one.
type RuleDeclaration = type[Rule] | type[RemovedRule]

# Every declaration `@rule` has seen in this process, in the order their modules were imported. A rules
# package's registry keeps those whose module lies in it.
_declared: list[RuleDeclaration] = []


# The type parameter only carries the decorated class's own type through, so a rule's name still names its class
# for the type checker; it ranges over no input kind, and the registry takes none, as adr-009 states. Without the
# parameter, every decorated name would be retyped as `RuleDeclaration`, and a rule's own fields and `check` would
# no longer type-check at its call sites.
def rule[T: Rule | RemovedRule](declaration: type[T]) -> type[T]:
    """Register a rule's class, or a removed rule, as its module is imported.

    Args:
        declaration: The class that declares the rule.

    Returns:
        The class unchanged.
    """
    _declared.append(declaration)
    return declaration


def declared_rules() -> tuple[RuleDeclaration, ...]:
    """Every declaration `@rule` has registered in this process, from every package, in the order seen."""
    return tuple(_declared)
