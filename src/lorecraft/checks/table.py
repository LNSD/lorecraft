"""The rule table: the rules a run enables, each with the severity it reports at, grouped by what it reads.

The table is built once per run, before any subject is checked. Until a configuration sets levels, it is built
from a registry and each rule's default level: a rule at `warn` reports warnings, one at `deny` errors, and one at
`allow` is not in the table, so it never runs and what it reads may never be computed. Removed rules and engine
conditions are not rules a run enables, so the table never holds one.

A rule is partitioned by its base: the rules over a document, the rules over a skill, the rules over the
frontmatter, which the runner runs over documents and skills alike, the rules over a Markdown file, which the runner
runs over a document, a skill and a resource alike, the rules over a skill's file, which it runs over a skill and a
resource alike, and the rules over a layout entry. The rules over a document and over the frontmatter are also
grouped by the facet each declares, since the runner runs them over a document facet by facet. Each partition pairs
every rule in it with its severity, as an `EnabledRule`, so a rule the runner finds in a partition always has a
severity to report at.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Self, assert_never

from lorecraft.rules.declaration import EngineCondition, Level, RemovedRule, Rule, Severity
from lorecraft.rules.registry import Registry
from lorecraft.rules.subject import (
    DocumentRule,
    Facet,
    FrontmatterRule,
    LayoutEntryRule,
    MarkdownRule,
    SkillFileRule,
    SkillRule,
)


class UnknownRuleBaseError(TypeError):
    """A rule derives from no base the table knows, so no partition holds it and it would never run.

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
        rule: The rule class, whose `check` the runner calls on the context its partition reads.
        severity: The severity each of the rule's occurrences is reported at.
    """

    rule: type[R]
    severity: Severity


class RuleTable:
    """The enabled rules of one run, each with its severity, partitioned by base in code order."""

    _document_rules: tuple[EnabledRule[DocumentRule], ...]
    _document_rules_by_facet: dict[Facet, tuple[EnabledRule[DocumentRule], ...]]
    _skill_rules: tuple[EnabledRule[SkillRule], ...]
    _markdown_rules: tuple[EnabledRule[MarkdownRule], ...]
    _skill_file_rules: tuple[EnabledRule[SkillFileRule], ...]
    _layout_rules: tuple[EnabledRule[LayoutEntryRule], ...]
    _frontmatter_rules: tuple[EnabledRule[FrontmatterRule], ...]
    _frontmatter_rules_by_facet: dict[Facet, tuple[EnabledRule[FrontmatterRule], ...]]

    def __init__(self, severities: Mapping[type[Rule], Severity]) -> None:
        """Hold the enabled rules, and partition them by the base each derives from.

        Args:
            severities: Each enabled rule, mapped to the severity its occurrences are reported at; a rule absent
                from it does not run.

        Raises:
            UnknownRuleBaseError: If a rule derives from no base the table partitions by.
        """
        document_rules: list[EnabledRule[DocumentRule]] = []
        skill_rules: list[EnabledRule[SkillRule]] = []
        markdown_rules: list[EnabledRule[MarkdownRule]] = []
        skill_file_rules: list[EnabledRule[SkillFileRule]] = []
        layout_rules: list[EnabledRule[LayoutEntryRule]] = []
        frontmatter_rules: list[EnabledRule[FrontmatterRule]] = []
        for rule_class in sorted(severities, key=_printed_code):
            # The rule hierarchy is open, so the chain cannot close with `assert_never`: a rule over a base with no
            # partition here is a defect, raised before any subject is checked.
            if issubclass(rule_class, DocumentRule):
                document_rules.append(EnabledRule(rule_class, severities[rule_class]))
            elif issubclass(rule_class, SkillRule):
                skill_rules.append(EnabledRule(rule_class, severities[rule_class]))
            elif issubclass(rule_class, MarkdownRule):
                markdown_rules.append(EnabledRule(rule_class, severities[rule_class]))
            elif issubclass(rule_class, SkillFileRule):
                skill_file_rules.append(EnabledRule(rule_class, severities[rule_class]))
            elif issubclass(rule_class, LayoutEntryRule):
                layout_rules.append(EnabledRule(rule_class, severities[rule_class]))
            elif issubclass(rule_class, FrontmatterRule):
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
        self._layout_rules = tuple(layout_rules)
        self._frontmatter_rules = tuple(frontmatter_rules)
        self._frontmatter_rules_by_facet = {}
        for facet in Facet:
            self._frontmatter_rules_by_facet[facet] = tuple(
                enabled for enabled in frontmatter_rules if enabled.rule.GOVERNED_BY is facet
            )

    @classmethod
    def from_registry(cls, registry: Registry) -> Self:
        """Enable every rule of a registry at its default level, with no configuration and no selection.

        Args:
            registry: The rules the run may enable; its removed rules and engine conditions are left out.

        Raises:
            UnknownRuleBaseError: If an enabled rule derives from no base the table partitions by.
        """
        severities: dict[type[Rule], Severity] = {}
        for declaration in registry.rules:
            # A `match` class pattern tests an instance, not a class, so the branch on a declaration's kind is an
            # `issubclass` chain, closed by `assert_never` as the registry's own is.
            if issubclass(declaration, Rule):
                severity = _default_severity(declaration.LEVEL)
                if severity is not None:
                    severities[declaration] = severity
            elif issubclass(declaration, RemovedRule):
                continue
            elif issubclass(declaration, EngineCondition):
                continue
            else:
                assert_never(declaration)
        return cls(severities)

    @property
    def document_rules(self) -> tuple[EnabledRule[DocumentRule], ...]:
        """Each enabled rule over a document, whatever facet it reads, in code order; empty when none is."""
        return self._document_rules

    def document_rules_governed_by(self, facet: Facet) -> tuple[EnabledRule[DocumentRule], ...]:
        """Each enabled rule over a document that reads this facet, with its severity, in code order.

        Args:
            facet: The facet the rules declare in `GOVERNED_BY`; the result is empty when no enabled rule reads it.
        """
        return self._document_rules_by_facet[facet]

    @property
    def skill_rules(self) -> tuple[EnabledRule[SkillRule], ...]:
        """Each enabled rule over a skill, with its severity, in code order; empty when none is."""
        return self._skill_rules

    @property
    def markdown_rules(self) -> tuple[EnabledRule[MarkdownRule], ...]:
        """Each enabled rule over a Markdown file, with its severity, in code order; empty when none is."""
        return self._markdown_rules

    @property
    def skill_file_rules(self) -> tuple[EnabledRule[SkillFileRule], ...]:
        """Each enabled rule over a skill's file, with its severity, in code order; empty when none is."""
        return self._skill_file_rules

    @property
    def layout_rules(self) -> tuple[EnabledRule[LayoutEntryRule], ...]:
        """Each enabled rule over a layout entry, with its severity, in code order; empty when none is."""
        return self._layout_rules

    @property
    def frontmatter_rules(self) -> tuple[EnabledRule[FrontmatterRule], ...]:
        """Each enabled rule over the frontmatter, with its severity, in code order; empty when none is."""
        return self._frontmatter_rules

    def frontmatter_rules_governed_by(self, facet: Facet) -> tuple[EnabledRule[FrontmatterRule], ...]:
        """Each enabled rule over the frontmatter that a document is gated on this facet for, in code order.

        Args:
            facet: The facet the rules declare in `GOVERNED_BY`; the result is empty when no enabled rule reads it.
        """
        return self._frontmatter_rules_by_facet[facet]


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
