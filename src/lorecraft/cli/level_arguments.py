"""The values of `-A`, `-W` and `-D`, confirmed against the rule index at the command line boundary."""

from dataclasses import dataclass
from typing import Protocol, Self

from lorecraft.core.error import Error
from lorecraft.rules import index
from lorecraft.rules.identity import Level, RuleCode
from lorecraft.rules.index import RuleRow


class RuleIndex(Protocol):
    """The command-line rule index, which needs only lookup by code or alias."""

    def find(self, key: str, /) -> index.RuleIndexRow | None:
        """Return the indexed row for a key, if any."""


@dataclass(frozen=True, slots=True)
class AllRulesTarget:
    """The `ALL` target for a level flag."""

    def __str__(self) -> str:
        """The reserved selector's spelling."""
        return 'ALL'


@dataclass(frozen=True, slots=True)
class Warnings:
    """The rules whose default level is warning, selected by `warnings`."""

    def __str__(self) -> str:
        """The reserved selector's spelling."""
        return 'warnings'


type LevelTarget = AllRulesTarget | Warnings | RuleCode


class InvalidLevelArgumentError(Error):
    """A level flag argument is empty, malformed, unknown or reserved for another flag.

    Attributes:
        value: The argument as typed.
        flag: The level flag that received it.
        reason: Why the argument is not accepted.
    """

    value: str
    flag: str
    reason: str

    def __init__(self, value: str, flag: str, reason: str) -> None:
        self.value = value
        self.flag = flag
        self.reason = reason
        super().__init__(f'{flag} {value!r}: {reason}')


class ConflictingLevelArgumentError(Error):
    """One rule is assigned different levels on the command line.

    Attributes:
        code: The canonical code of the rule with conflicting assignments.
        first: The first level assigned.
        second: The conflicting level assigned later.
    """

    code: str
    first: Level
    second: Level

    def __init__(self, code: str, first: Level, second: Level) -> None:
        self.code = code
        self.first = first
        self.second = second
        super().__init__(f'{code} has conflicting levels {first.value!r} and {second.value!r}')


@dataclass(frozen=True, slots=True)
class LevelArgument:
    """One level flag and the rule code or reserved selector it names."""

    level: Level
    target: LevelTarget

    @classmethod
    def parse(cls, raw: str, level: Level, rule_index: RuleIndex = index) -> Self:
        """Parse one flag value, accepting only active full codes, aliases, and its reserved selectors."""
        value = raw.strip()
        flag = f'--{level.value}'
        if not value:
            raise InvalidLevelArgumentError(raw, flag, 'write a full rule code, alias code, or ALL')
        if value == 'ALL':
            return cls(level, AllRulesTarget())
        if value == 'warnings' and level is Level.DENY:
            return cls(level, Warnings())
        row = rule_index.find(value)
        if isinstance(row, RuleRow):
            if value == row.code or value in row.aliases:
                return cls(level, _rule_code(row.code))
        raise InvalidLevelArgumentError(raw, flag, 'write a full active rule code, alias code, or ALL')


def validate_level_arguments(arguments: tuple[LevelArgument, ...]) -> None:
    """Refuse conflicting levels for a code; an alias has already resolved to its rule's code."""
    levels: dict[LevelTarget, Level] = {}
    for argument in arguments:
        previous = levels.get(argument.target)
        if previous is not None and previous != argument.level:
            raise ConflictingLevelArgumentError(str(argument.target), previous, argument.level)
        levels[argument.target] = argument.level


def _rule_code(code: str) -> RuleCode:
    """Build the identity of an indexed active rule when an actual level flag is parsed."""
    # These imports stay on the argument path: importing `check --help` must not load the rule group table.
    from lorecraft import rules
    from lorecraft.rules.declaration import Rule
    from lorecraft.rules.registry import Registry

    declaration = Registry.load(rules).find(code)
    if declaration is None or not issubclass(declaration, Rule):
        raise RuntimeError(f'active rule index row {code!r} is not held by the rules registry')
    return declaration.CODE
