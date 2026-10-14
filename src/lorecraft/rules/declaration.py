"""How a rule is declared: its identity values and the rule class that declares it.

A rule is one class. The class is the declaration and the check: its code, name, default level, the
release it is stable since and its documentation, as class attributes and the docstring, and the `check`
classmethod that judges its subject. Each subject kind has one base class deriving from `ContentRule` or
`LayoutRule`, whose abstract `check` fixes the context it reads, so a rule picks its subject by picking its base.
A retired rule is a `RemovedRule`, which is not a `Rule`, so it can never be built as one or reported. What the
engine itself reports about a subject, such as a file that does not decode, is an `EngineCondition`: declared
and rendered like a rule, but with an `EngineCode`, a fixed `Severity` in place of a level, and no `check`. It derives
from `FileCondition` or `EntryCondition`, as a rule does from `ContentRule` or `LayoutRule`.

A `Release`, a `RuleName`, a `RuleGroupPrefix`, a `LinterName` and an `UpstreamCode` are value objects, which
cannot know whether their caller wrote a literal or parsed a file or a command line, so their format raises an
`Error` variant. A `RuleGroup`, a `RuleCode` and an `AliasCode` are records built from those values. Two of their
fields are plain values with a bound: a group's title and a code's number. No file and no command line supplies
either, since a user names a group by its prefix and a rule by its code, so one out of bounds is a defect in the
package, rejected with a `ValueError` rather than an `Error` that the command line would report as the user's
fault.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from string import ascii_uppercase
from typing import ClassVar, Final, Self

from lorecraft.core.error import Error
from lorecraft.core.path import RootRelativePath
from lorecraft.project.syntax import LineNumber

from .identity import ALL_RULES_SELECTOR, Level, Release, RuleName
from .location import (
    EntryLabel,
    EntrySubdiagnostic,
    Here,
    Label,
    Primary,
    Subdiagnostic,
    WholeSubject,
)


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


@dataclass(frozen=True, slots=True, kw_only=True)
class Rule(ABC):
    """A rule, declared and checked by its class.

    An instance of a rule is one occurrence of it, at one place, which is why its `check` returns `tuple[Self, ...]`.

    A subclass declares the rule in its class attributes and its docstring, adds the data of its own condition
    and the context its diagnostic needs as fields, and renders every part of the diagnostic from those fields.
    It names no subject: the run that checked the subject locates it.

    A rule never derives from this class directly, but from its subject kind's base, which derives from
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


@dataclass(frozen=True, slots=True, kw_only=True)
class EngineCondition(ABC):
    """A condition the engine reports about a subject before any rule judges it, such as a file that does not decode.

    It is declared like a rule, with a code, a name, the release it is stable since and its documentation, and an
    instance of it is one occurrence that renders like a rule's. It is not a `Rule`: it has no level, so nothing
    can turn it off, and no `check`, since the engine finds it, not a judgment of a subject. Its severity is fixed
    on the class, and its code is an `EngineCode`, always in the engine's group.

    A condition never derives from this class directly, but from the base of the subject it is about: a
    `FileCondition` for a file the engine read, an `EntryCondition` for a path whose content it has not read, such as
    a directory, a skill entry or a file it could not read, which points at no line.

    Attributes:
        CODE: The condition's code, in the engine's group, such as `LC001`.
        NAME: The condition's kebab-case name, such as `invalid-utf8`.
        SINCE: The release the condition is stable since.
        SEVERITY: The severity every occurrence of the condition is reported at.
    """

    CODE: ClassVar[EngineCode]
    NAME: ClassVar[RuleName]
    SINCE: ClassVar[Release]
    SEVERITY: ClassVar[Severity]

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
class FileCondition(EngineCondition):
    """A condition of a file, which has lines: it points at one, or at the file as a whole.

    Its labels and sub-diagnostics may point at a line of the file or elsewhere.
    """

    @abstractmethod
    def primary(self) -> Primary:
        """A line of the file, or the file as a whole."""

    def labels(self) -> tuple[Label, ...]:
        """The labelled locations of this occurrence; none, so the primary location is unlabelled."""
        return ()

    def children(self) -> tuple[Subdiagnostic, ...]:
        """The help and notes printed under the message; none."""
        return ()


@dataclass(frozen=True, slots=True, kw_only=True)
class EntryCondition(EngineCondition):
    """A condition of a path whose content the engine has not read, so it points at no line.

    Such a path is a directory, a skill entry, or a file the engine could not read.

    Its labels and sub-diagnostics can only point at another file.
    """

    def primary(self) -> WholeSubject:
        """The entry itself."""
        return WholeSubject()

    def labels(self) -> tuple[EntryLabel, ...]:
        """The labelled locations of this occurrence; none, so the entry is unlabelled."""
        return ()

    def children(self) -> tuple[EntrySubdiagnostic, ...]:
        """The help and notes printed under the message; none."""
        return ()


# What `@rule` registers: a rule in service, as its class, a retired one, or an engine condition of a file or of an
# entry. `EngineCondition` itself is left out, so a condition of neither base is a type error where it is declared.
type RuleDeclaration = type[Rule | RemovedRule | FileCondition | EntryCondition]
