"""How a rule is declared: the rule classes and the engine conditions, each one class that declares and checks.

A rule is one class. The class is the declaration and the check: its code, name, default level, the
release it is stable since and its documentation, as class attributes and the docstring, and the `check`
classmethod that judges its subject. Each subject kind has one base class deriving from `ContentRule` or
`LayoutRule`, whose abstract `check` fixes the context it reads, so a rule picks its subject by picking its base.
A retired rule is a `RemovedRule`, which is not a `Rule`, so it can never be built as one or reported. What the
engine itself reports about a subject, such as a file that does not decode, is an `EngineCondition`: declared
and rendered like a rule, but with an `EngineCode`, a fixed `Severity` in place of a level, and no `check`. It derives
from `FileCondition` or `EntryCondition`, as a rule does from `ContentRule` or `LayoutRule`.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar

from lorecraft.core.path import RootRelativePath
from lorecraft.project.syntax import LineNumber

from .identity import AliasCode, EngineCode, Level, Release, RuleCode, RuleName, Severity
from .location import (
    EntryLabel,
    EntrySubdiagnostic,
    Here,
    Label,
    Primary,
    Subdiagnostic,
    WholeSubject,
)


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
