"""The values of `-A`, `-W` and `-D`, confirmed against the rule index at the command line boundary."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from lorecraft.core.error import Error
from lorecraft.rules import index
from lorecraft.rules.identity import Level
from lorecraft.rules.index import RuleRow
from lorecraft.rules.level_resolution import WrittenSelector

from .rule_key import IndexRuleNotInRegistryError, RuleIndex, RuleKey

if TYPE_CHECKING:
    from lorecraft.rules.identity import RuleCode
    from lorecraft.rules.registry import Registry


@dataclass(frozen=True, slots=True)
class AllRulesTarget:
    """The `ALL` target for a level flag."""

    def __str__(self) -> str:
        """The reserved selector's spelling."""
        return 'ALL'


@dataclass(frozen=True, slots=True)
class RuleCodeTarget:
    """A canonical rule key, plus an alias spelling when the user supplied one.

    Attributes:
        key: The canonical active rule key from the index.
        alias: The alias spelling exactly as the user typed it, or None for a canonical code.
    """

    key: RuleKey
    alias: WrittenSelector | None = field(default=None, compare=False, hash=False)

    def __str__(self) -> str:
        """The canonical rule code."""
        return self.key.text

    def to_rule_code(self, registry: Registry) -> RuleCode:
        """Build the rule-side identity after the check flow loads the registry.

        Args:
            registry: The declarations held by the rules package.

        Raises:
            IndexRuleNotInRegistryError: If the index's active rule code has no active rule declaration.
        """
        # Keep rule imports local so `check --help` does not load the rule declarations.
        from lorecraft.rules.declaration import Rule

        declaration = self.key.to_declaration(registry)
        if issubclass(declaration, Rule):
            return declaration.CODE
        # An active rule code resolving to a removed rule or engine condition means the generated index is stale.
        else:
            raise IndexRuleNotInRegistryError(self.key.text)


type LevelTarget = AllRulesTarget | RuleCodeTarget


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
        """Describe a rejected selector.

        Args:
            value: The argument as typed.
            flag: The flag that received it.
            reason: Why the value is not accepted.
        """
        self.value = value
        self.flag = flag
        self.reason = reason
        super().__init__(f'{flag} {value!r}: {reason}')


class ConflictingLevelArgumentError(Error):
    """One command-line target is assigned different levels.

    Attributes:
        target: The target with conflicting assignments.
        first: The first level assigned.
        second: The conflicting level assigned later.
    """

    target: LevelTarget
    first: Level
    second: Level

    def __init__(self, target: LevelTarget, first: Level, second: Level) -> None:
        """Describe conflicting assignments to one target.

        Args:
            target: The target assigned conflicting levels.
            first: The first level assigned.
            second: The conflicting level assigned later.
        """
        self.target = target
        self.first = first
        self.second = second
        super().__init__(f'{target} has conflicting levels {first.value!r} and {second.value!r}')


@dataclass(frozen=True, slots=True)
class DenyWarnings:
    """The `-D warnings` argument, separate from ordinary level targets."""

    def __str__(self) -> str:
        """The reserved selector's spelling."""
        return 'warnings'


@dataclass(frozen=True, slots=True)
class LevelArgument:
    """One level flag and the rule code or reserved selector it names.

    Attributes:
        level: The level to apply to matching rules.
        target: The active rule code or `ALL`.
    """

    level: Level
    target: LevelTarget

    @classmethod
    def parse(cls, raw: str, level: Level, rule_index: RuleIndex = index) -> LevelArgument | DenyWarnings:
        """Parse one flag value, accepting only active full codes, aliases, and its reserved selectors.

        Args:
            raw: The selector as the user typed it.
            level: The level flag receiving the selector.
            rule_index: The lightweight rule index used to validate and canonicalize the selector.

        Raises:
            InvalidLevelArgumentError: If the selector is malformed, unknown, or reserved for another flag.
        """
        value = raw.strip()
        flag = f'--{level.value}'
        if not value:
            raise InvalidLevelArgumentError(raw, flag, 'write a full rule code, alias code, or ALL')
        if value == 'ALL':
            return cls(level, AllRulesTarget())
        if value == 'warnings' and level is Level.DENY:
            return DenyWarnings()
        row = rule_index.find(value)
        if isinstance(row, RuleRow):
            if value == row.code or value in row.aliases:
                alias = WrittenSelector(value) if value != row.code else None
                return cls(level, RuleCodeTarget(RuleKey(row.code), alias))
        reason = (
            'warnings is reserved for --deny'
            if value == 'warnings'
            else 'write a full active rule code, alias code, or ALL'
        )
        raise InvalidLevelArgumentError(raw, flag, reason)


type ParsedLevelArgument = LevelArgument | DenyWarnings


def validate_level_arguments(arguments: tuple[ParsedLevelArgument, ...]) -> None:
    """Refuse conflicting levels for a code; aliases compare by their canonical code.

    Args:
        arguments: The parsed values of all level flags in this invocation.

    Raises:
        ConflictingLevelArgumentError: If one rule or `ALL` receives different levels.
    """
    levels: dict[LevelTarget, Level] = {}
    for argument in arguments:
        if isinstance(argument, DenyWarnings):
            continue
        previous = levels.get(argument.target)
        if previous is not None and previous != argument.level:
            raise ConflictingLevelArgumentError(argument.target, previous, argument.level)
        levels[argument.target] = argument.level
