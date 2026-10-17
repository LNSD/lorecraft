"""The rule table: the rules a run enables, each with the severity it reports at, grouped by what it reads.

The table is built once per run, before any subject is checked. Until a configuration sets levels, it is built
from a registry and each rule's default level: a rule at `warn` reports warnings, one at `deny` errors, and one at
`allow` is not in the table, so it never runs and what it reads may never be computed. Removed rules and engine
conditions are not rules a run enables, so the table never holds one. A one-run selection then leaves out every rule
it does not keep; it filters, and never enables a rule its level leaves off.

A rule is partitioned by its base: the rules over a document, the rules over a skill, the rules over the
frontmatter, which the runner runs over documents and skills alike, the rules over a Markdown file, which the runner
runs over a document, a skill and a resource alike, the rules over a skill's file, which it runs over a skill and a
resource alike, the rules over a symlink of the skill layout, and the rules over a directory named like a reserved
corpus. The rules over a document and over the frontmatter are also
grouped by the facet each declares, since the runner runs them over a document facet by facet. Each partition pairs
every rule in it with its severity, as an `EnabledRule`, so a rule the runner finds in a partition always has a
severity to report at. A partition holds only queried rules, so the runner finds a query to resolve for every rule
in it; a rule that names none is rejected as the table is built.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Self, assert_never

from .declaration import Rule
from .identity import Level, Severity
from .registry import Registry
from .selection import RuleSelection
from .subject import (
    Facet,
    QueriedCorpusDirectoryRule,
    QueriedDocumentRule,
    QueriedFrontmatterRule,
    QueriedMarkdownRule,
    QueriedSkillFileRule,
    QueriedSkillRule,
    QueriedSymlinkRule,
)


class UnknownRuleBaseError(TypeError):
    """A rule derives from no queried base the table knows, so no partition holds it and it would never run.

    The rule hierarchy is open, so no type closes the set of bases a rule may derive from; the table rejects such a
    rule as it is built, before any subject.

    Attributes:
        rule: The rule that derives from no base the table partitions by.
    """

    rule: type[Rule]

    def __init__(self, rule: type[Rule]) -> None:
        self.rule = rule
        super().__init__(f'rule {rule.__qualname__} ({rule.CODE}) derives from no base the rule table knows')


@dataclass(frozen=True, slots=True)
class EnabledRule[R: Rule]:
    """A rule a run enables, with the severity its occurrences are reported at.

    Attributes:
        rule: The rule class, whose `query` and `judge` the runner calls on the partition's subjects.
        severity: The severity each of the rule's occurrences is reported at.
    """

    rule: type[R]
    severity: Severity


class RuleTable:
    """The enabled rules of one run, each with its severity, partitioned by base in code order."""

    _document_rules: tuple[EnabledRule[QueriedDocumentRule[Any]], ...]
    _document_rules_by_facet: dict[Facet, tuple[EnabledRule[QueriedDocumentRule[Any]], ...]]
    _skill_rules: tuple[EnabledRule[QueriedSkillRule[Any]], ...]
    _markdown_rules: tuple[EnabledRule[QueriedMarkdownRule[Any]], ...]
    _skill_file_rules: tuple[EnabledRule[QueriedSkillFileRule[Any]], ...]
    _symlink_rules: tuple[EnabledRule[QueriedSymlinkRule[Any]], ...]
    _corpus_directory_rules: tuple[EnabledRule[QueriedCorpusDirectoryRule[Any]], ...]
    _frontmatter_rules: tuple[EnabledRule[QueriedFrontmatterRule[Any]], ...]
    _frontmatter_rules_by_facet: dict[Facet, tuple[EnabledRule[QueriedFrontmatterRule[Any]], ...]]

    def __init__(self, severities: Mapping[type[Rule], Severity]) -> None:
        """Hold the enabled rules, and partition them by the base each derives from.

        Args:
            severities: Each enabled rule, mapped to the severity its occurrences are reported at; a rule absent
                from it does not run.

        Raises:
            UnknownRuleBaseError: If a rule derives from no base the table partitions by.
        """
        document_rules: list[EnabledRule[QueriedDocumentRule[Any]]] = []
        skill_rules: list[EnabledRule[QueriedSkillRule[Any]]] = []
        markdown_rules: list[EnabledRule[QueriedMarkdownRule[Any]]] = []
        skill_file_rules: list[EnabledRule[QueriedSkillFileRule[Any]]] = []
        symlink_rules: list[EnabledRule[QueriedSymlinkRule[Any]]] = []
        corpus_directory_rules: list[EnabledRule[QueriedCorpusDirectoryRule[Any]]] = []
        frontmatter_rules: list[EnabledRule[QueriedFrontmatterRule[Any]]] = []
        for rule_class in sorted(severities, key=_printed_code):
            # The rule hierarchy is open, so the chain cannot close with `assert_never`: a rule over a base with no
            # partition here is a defect, raised before any subject is checked.
            if issubclass(rule_class, QueriedDocumentRule):
                document_rules.append(EnabledRule(rule_class, severities[rule_class]))
            elif issubclass(rule_class, QueriedSkillRule):
                skill_rules.append(EnabledRule(rule_class, severities[rule_class]))
            elif issubclass(rule_class, QueriedMarkdownRule):
                markdown_rules.append(EnabledRule(rule_class, severities[rule_class]))
            elif issubclass(rule_class, QueriedSkillFileRule):
                skill_file_rules.append(EnabledRule(rule_class, severities[rule_class]))
            elif issubclass(rule_class, QueriedSymlinkRule):
                symlink_rules.append(EnabledRule(rule_class, severities[rule_class]))
            elif issubclass(rule_class, QueriedCorpusDirectoryRule):
                corpus_directory_rules.append(EnabledRule(rule_class, severities[rule_class]))
            elif issubclass(rule_class, QueriedFrontmatterRule):
                frontmatter_rules.append(EnabledRule(rule_class, severities[rule_class]))
            else:
                raise UnknownRuleBaseError(rule_class)
        self._document_rules = tuple(document_rules)
        self._document_rules_by_facet = {}
        for facet in Facet:
            self._document_rules_by_facet[facet] = tuple(
                enabled for enabled in document_rules if enabled.rule.GOVERNED_BY is facet
            )
        self._skill_rules = tuple(skill_rules)
        self._markdown_rules = tuple(markdown_rules)
        self._skill_file_rules = tuple(skill_file_rules)
        self._symlink_rules = tuple(symlink_rules)
        self._corpus_directory_rules = tuple(corpus_directory_rules)
        self._frontmatter_rules = tuple(frontmatter_rules)
        self._frontmatter_rules_by_facet = {}
        for facet in Facet:
            self._frontmatter_rules_by_facet[facet] = tuple(
                enabled for enabled in frontmatter_rules if enabled.rule.GOVERNED_BY is facet
            )

    @classmethod
    def from_registry(cls, registry: Registry, selection: RuleSelection) -> Self:
        """Enable each rule of a registry the selection keeps, at its default level, with no configuration.

        Args:
            registry: The rules the run may enable; its removed rules and engine conditions are left out.
            selection: The rules this run keeps; a rule it leaves out is not enabled, whatever its level.

        Raises:
            UnknownRuleBaseError: If an enabled rule derives from no base the table partitions by.
        """
        severities: dict[type[Rule], Severity] = {}
        for rule_class in registry.rules_in_service:
            if not selection.is_kept(rule_class.CODE):
                continue
            severity = _default_severity(rule_class.LEVEL)
            if severity is not None:
                severities[rule_class] = severity
        return cls(severities)

    @property
    def document_rules(self) -> tuple[EnabledRule[QueriedDocumentRule[Any]], ...]:
        """Each enabled rule over a document, whatever facet it reads, in code order; empty when none is."""
        return self._document_rules

    def document_rules_governed_by(self, facet: Facet) -> tuple[EnabledRule[QueriedDocumentRule[Any]], ...]:
        """Each enabled rule over a document that reads this facet, with its severity, in code order.

        Args:
            facet: The facet the rules declare in `GOVERNED_BY`; the result is empty when no enabled rule reads it.
        """
        return self._document_rules_by_facet[facet]

    @property
    def skill_rules(self) -> tuple[EnabledRule[QueriedSkillRule[Any]], ...]:
        """Each enabled rule over a skill, with its severity, in code order; empty when none is."""
        return self._skill_rules

    @property
    def markdown_rules(self) -> tuple[EnabledRule[QueriedMarkdownRule[Any]], ...]:
        """Each enabled rule over a Markdown file, with its severity, in code order; empty when none is."""
        return self._markdown_rules

    @property
    def skill_file_rules(self) -> tuple[EnabledRule[QueriedSkillFileRule[Any]], ...]:
        """Each enabled rule over a skill's file, with its severity, in code order; empty when none is."""
        return self._skill_file_rules

    @property
    def symlink_rules(self) -> tuple[EnabledRule[QueriedSymlinkRule[Any]], ...]:
        """Each enabled rule over a layout symlink, with its severity, in code order; empty when none is."""
        return self._symlink_rules

    @property
    def corpus_directory_rules(self) -> tuple[EnabledRule[QueriedCorpusDirectoryRule[Any]], ...]:
        """Each enabled rule over a directory named like a reserved corpus, with its severity, in code order."""
        return self._corpus_directory_rules

    @property
    def frontmatter_rules(self) -> tuple[EnabledRule[QueriedFrontmatterRule[Any]], ...]:
        """Each enabled rule over the frontmatter, with its severity, in code order; empty when none is."""
        return self._frontmatter_rules

    def frontmatter_rules_governed_by(self, facet: Facet) -> tuple[EnabledRule[QueriedFrontmatterRule[Any]], ...]:
        """Each enabled rule over the frontmatter that a document is gated on this facet for, in code order.

        Args:
            facet: The facet the rules declare in `GOVERNED_BY`; the result is empty when no enabled rule reads it.
        """
        return self._frontmatter_rules_by_facet[facet]


def selected_rules_left_off(registry: Registry, selection: RuleSelection) -> tuple[type[Rule], ...]:
    """Each rule a selection names by its code, and keeps, that its level leaves off, in code order.

    A selection never enables a rule, so such a rule does not run; the command line warns of each. A rule kept only
    through a broader selector, its group, a prefix of its code or `ALL`, is not named, so it is not among them.

    Args:
        registry: The rules the run may enable.
        selection: The rules this run keeps.
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
    """The severity a rule at this level reports at, or `None` for a level at which the rule does not run.

    Args:
        level: The default level a rule declares as its `LEVEL`; `allow` gives `None`.
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
    """The rule's code as output prints it, the key that orders each partition.

    Args:
        rule: The rule class whose code is printed.
    """
    return str(rule.CODE)
