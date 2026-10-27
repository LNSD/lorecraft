"""The rule table: rules a run enables, indexed by item type and declared gate.

The table is built once per run, before any subject is checked. It retains each enabled rule's resolution and derives
the severity of its occurrences from that level. Rules left off by their default level are absent; removed rules and
engine conditions are not enabled rules. Item rules are indexed once by item type and gate, while
rules over layout symlinks and reserved-corpus directories keep separate partitions. A rule's closed gate declaration
determines which index buckets contain it. Only queried rules can be indexed, so each rule in a bucket has a query
for the runner to resolve.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Self

from lorecraft.project.item import ItemType

from .declaration import Rule
from .identity import Level, Severity
from .level_resolution import (
    AllowedLevel,
    DefaultLevel,
    ElevatedWarning,
    OverriddenLevel,
    ReportingResolution,
    ResolvedLevels,
)
from .registry import Registry
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
        resolution: The typed source, level and selector that produced the effective level.
    """

    rule: type[R]
    resolution: ReportingResolution

    @property
    def severity(self) -> Severity:
        """The severity determined by the reporting resolution variant."""
        return self.resolution.severity


# The table combines rules with unrelated query fact types; each rule retains its own query type at dispatch.
type QueriedItem = QueriedItemRule[Any]


class RuleTable:
    """The enabled rules of one run, indexed by item type and gate, plus separate layout partitions."""

    _item_rules: dict[tuple[ItemType, Gate], tuple[EnabledRule[QueriedItem], ...]]
    # Layout rules share a partition despite having unrelated query fact types.
    _symlink_rules: tuple[EnabledRule[QueriedSymlinkRule[Any]], ...]
    # Corpus-directory rules likewise preserve each rule's query type until dispatch.
    _corpus_directory_rules: tuple[EnabledRule[QueriedCorpusDirectoryRule[Any]], ...]

    def __init__(
        self,
        resolutions: Mapping[type[Rule], ReportingResolution],
    ) -> None:
        """Hold resolved rules under their declared gates and preserve layout partitions.

        Args:
            resolutions: The level resolution for each enabled rule.

        Raises:
            UnknownRuleBaseError: If a rule has no supported query base.
        """
        item_rules: dict[tuple[ItemType, Gate], list[EnabledRule[QueriedItem]]] = {}
        symlink_rules: list[EnabledRule[QueriedSymlinkRule[Any]]] = []
        corpus_directory_rules: list[EnabledRule[QueriedCorpusDirectoryRule[Any]]] = []
        for rule_class in sorted(resolutions, key=_printed_code):
            if issubclass(rule_class, QueriedSymlinkRule):
                symlink_rules.append(EnabledRule(rule_class, resolutions[rule_class]))
            elif issubclass(rule_class, QueriedCorpusDirectoryRule):
                corpus_directory_rules.append(EnabledRule(rule_class, resolutions[rule_class]))
            elif issubclass(rule_class, QueriedItemRule):
                enabled = EnabledRule(rule_class, resolutions[rule_class])
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
        levels: ResolvedLevels,
        deny_warnings: bool = False,
    ) -> Self:
        """Enable each in-service rule at its resolved level, leaving allow-level rules out.

        Args:
            registry: The rules the run may enable; removed rules and engine conditions are left out.
            levels: Overrides, ordered from lowest to highest precedence; empty when no levels are configured.
            deny_warnings: Elevate every resolved warning to an error after resolving explicit levels.

        Raises:
            UnknownRuleBaseError: If an enabled rule has no supported query base.
        """
        resolutions: dict[type[Rule], ReportingResolution] = {}
        for rule_class in registry.rules_in_service:
            resolution = levels.resolution_for(rule_class.CODE, rule_class.LEVEL)
            if isinstance(resolution, AllowedLevel):
                continue
            resolutions[rule_class] = _reporting_resolution(resolution, rule_class.LEVEL, deny_warnings)
        return cls(resolutions)

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


def _printed_code(rule: type[Rule]) -> str:
    """The rule's printed code, used to order each index bucket.

    Args:
        rule: The rule whose printed code determines its position.
    """
    return str(rule.CODE)


def _reporting_resolution(
    resolution: DefaultLevel | OverriddenLevel,
    declared: Level,
    deny_warnings: bool,
) -> ReportingResolution:
    """Apply warning elevation and restore default provenance when an override resolves to the declared level.

    Args:
        resolution: The resolved default or override for the rule.
        declared: The level the rule declares.
        deny_warnings: Whether warnings are elevated to errors.
    """
    if deny_warnings and resolution.level is Level.WARN:
        if declared is Level.DENY:
            # A default-deny rule lowered by -W and raised back by -D warnings is its declared default again.
            return DefaultLevel(Level.DENY)
        return ElevatedWarning()
    if resolution.level is declared:
        # An override equal to the declared level has default provenance.
        return DefaultLevel(resolution.level)
    return resolution
