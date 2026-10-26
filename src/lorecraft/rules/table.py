"""The rule table: rules a run enables, indexed by item type and declared gate.

The table is built once per run, before any subject is checked. It pairs each enabled rule with the severity of its
occurrences. Rules left off by their default level or a run selection are absent; removed rules and engine
conditions are not enabled rules. Item rules are indexed once by item type and gate, while
rules over layout symlinks and reserved-corpus directories keep separate partitions. A rule's closed gate declaration
determines which index buckets contain it. Only queried rules can be indexed, so each rule in a bucket has a query
for the runner to resolve.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Self, assert_never

from lorecraft.project.item import ItemType

from .declaration import Rule
from .identity import Level, Severity
from .level_resolution import ResolvedLevels
from .registry import Registry
from .selection import RuleSelection
from .subject import (
    Gate,
    QueriedCorpusDirectoryRule,
    QueriedItemRule,
    QueriedSymlinkRule,
)


class UnknownRuleBaseError(TypeError):
    """A rule cannot enter the table because it has no supported query base.

    The rule hierarchy is open. The table rejects rules without a supported queried base before any subject is checked.

    Attributes:
        rule: The rule class rejected while building the table.
    """

    rule: type[Rule]

    def __init__(self, rule: type[Rule]) -> None:
        self.rule = rule
        super().__init__(f'rule {rule.__qualname__} ({rule.CODE}) has no supported query base')


@dataclass(frozen=True, slots=True)
class EnabledRule[R: Rule]:
    """A rule a run enables, with the severity its occurrences are reported at.

    Attributes:
        rule: The rule class to run.
        severity: The severity used for each occurrence.
    """

    rule: type[R]
    severity: Severity


# The table combines rules with unrelated query fact types; each rule retains its own query type at dispatch.
type QueriedItem = QueriedItemRule[Any]


class RuleTable:
    """The enabled rules of one run, indexed by item type and gate, plus separate layout partitions."""

    _item_rules: dict[tuple[ItemType, Gate], tuple[EnabledRule[QueriedItem], ...]]
    # Layout rules share a partition despite having unrelated query fact types.
    _symlink_rules: tuple[EnabledRule[QueriedSymlinkRule[Any]], ...]
    # Corpus-directory rules likewise preserve each rule's query type until dispatch.
    _corpus_directory_rules: tuple[EnabledRule[QueriedCorpusDirectoryRule[Any]], ...]

    def __init__(self, severities: Mapping[type[Rule], Severity]) -> None:
        """Hold enabled item rules under their declared gates and preserve layout partitions.

        Args:
            severities: Each enabled rule, mapped to the severity its occurrences are reported at.

        Raises:
            UnknownRuleBaseError: If a rule has no supported query base.
        """
        item_rules: dict[tuple[ItemType, Gate], list[EnabledRule[QueriedItem]]] = {}
        symlink_rules: list[EnabledRule[QueriedSymlinkRule[Any]]] = []
        corpus_directory_rules: list[EnabledRule[QueriedCorpusDirectoryRule[Any]]] = []
        for rule_class in sorted(severities, key=_printed_code):
            if issubclass(rule_class, QueriedSymlinkRule):
                symlink_rules.append(EnabledRule(rule_class, severities[rule_class]))
            elif issubclass(rule_class, QueriedCorpusDirectoryRule):
                corpus_directory_rules.append(EnabledRule(rule_class, severities[rule_class]))
            elif issubclass(rule_class, QueriedItemRule):
                enabled = EnabledRule(rule_class, severities[rule_class])
                for item_type, gate in rule_class.APPLIES_TO.items():
                    item_rules.setdefault((item_type, gate), []).append(enabled)
            else:
                raise UnknownRuleBaseError(rule_class)
        self._item_rules = {key: tuple(rules) for key, rules in item_rules.items()}
        self._symlink_rules = tuple(symlink_rules)
        self._corpus_directory_rules = tuple(corpus_directory_rules)

    @classmethod
    def from_registry(
        cls,
        registry: Registry,
        selection: RuleSelection,
        levels: ResolvedLevels | None = None,
    ) -> Self:
        """Enable each selected in-service rule at its resolved level, leaving allow-level rules out.

        Args:
            registry: The rules the run may enable; removed rules and engine conditions are left out.
            selection: The rules this run keeps; a rule it leaves out is not enabled.
            levels: Optional overrides, ordered from lowest to highest precedence.

        Raises:
            UnknownRuleBaseError: If an enabled rule has no supported query base.
        """
        severities: dict[type[Rule], Severity] = {}
        for rule_class in registry.rules_in_service:
            if not selection.is_kept(rule_class.CODE):
                continue
            level = rule_class.LEVEL if levels is None else levels.level_for(rule_class.CODE, rule_class.LEVEL)
            severity = _default_severity(level)
            if severity is not None:
                severities[rule_class] = severity
        return cls(severities)

    def item_rules(self, item_type: ItemType, gate: Gate) -> tuple[EnabledRule[QueriedItem], ...]:
        """Each enabled item rule gated for this item type and gate, in code order.

        Args:
            item_type: The item type to look up.
            gate: The applicability gate declared by a rule.
        """
        return self._item_rules.get((item_type, gate), ())

    @property
    def symlink_rules(self) -> tuple[EnabledRule[QueriedSymlinkRule[Any]], ...]:
        """Each enabled rule over a layout symlink, in code order."""
        return self._symlink_rules

    @property
    def corpus_directory_rules(self) -> tuple[EnabledRule[QueriedCorpusDirectoryRule[Any]], ...]:
        """Each enabled rule over a reserved-corpus directory, in code order."""
        return self._corpus_directory_rules


def selected_rules_left_off(registry: Registry, selection: RuleSelection) -> tuple[type[Rule], ...]:
    """Each selected rule the default level leaves off, in code order.

    Args:
        registry: The in-service rules available to the run.
        selection: The selection whose explicit rule codes may name allow-level rules.
    """
    left_off: list[type[Rule]] = []
    for rule_class in registry.rules_in_service:
        if (
            rule_class.CODE in selection.select
            and selection.is_kept(rule_class.CODE)
            and _default_severity(rule_class.LEVEL) is None
        ):
            left_off.append(rule_class)
    return tuple(left_off)


def _default_severity(level: Level) -> Severity | None:
    """The severity for a running level, or `None` when the level allows the rule off.

    Args:
        level: The rule's configured default level.
    """
    match level:
        case Level.ALLOW:
            return None
        case Level.WARN:
            return Severity.WARNING
        case Level.DENY:
            return Severity.ERROR
        case _:
            assert_never(level)


def _printed_code(rule: type[Rule]) -> str:
    """The rule's printed code, used to order each index bucket.

    Args:
        rule: The rule whose printed code determines its position.
    """
    return str(rule.CODE)
