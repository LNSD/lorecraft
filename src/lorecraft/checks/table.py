"""The rule table: the rules a run enables, each with the severity it reports at, grouped by what it reads.

The table is built once per run, before any subject is checked. Until a configuration sets levels, it is built
from a registry and each rule's default level: a rule at `warn` reports warnings, one at `deny` errors, and one at
`allow` is not in the table, so it never runs and what it reads may never be computed. Removed rules and engine
conditions are not rules a run enables, so the table never holds one.

A rule is partitioned by its base: the rules over a document, which the runner runs facet by facet, and the rules
over a skill. Each partition pairs every rule in it with its severity, as an `EnabledRule`, so a rule the runner finds
in a partition always has a severity to report at.

Every shipped rule still reads an input, so the table also keeps one partition per input kind; later changes move
those rules onto a context and remove these partitions.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Self, assert_never

from lorecraft.rules.declaration import EngineCondition, Level, RemovedRule, Rule, Severity
from lorecraft.rules.inputs import (
    FrontmatterBlockRule,
    HeadingsRule,
    LineCountRule,
    OutlineDivergenceRule,
    SchemaProblemsRule,
    TokenCountRule,
)
from lorecraft.rules.registry import Registry
from lorecraft.rules.subject import DocumentRule, Facet, SkillRule


class UnknownRuleInputError(TypeError):
    """A rule derives from no base the table knows, so no partition holds it and it would never run.

    The rule hierarchy is open, so no type closes the set of bases a rule may derive from; the table rejects such a
    rule as it is built, before any subject.

    Attributes:
        rule: The rule that derives from no base the table partitions by.
    """

    rule: type[Rule]

    def __init__(self, rule: type[Rule]) -> None:
        self.rule = rule
        super().__init__(f'rule {rule.__qualname__} ({rule.CODE}) reads no input the rule table knows')


@dataclass(frozen=True, slots=True)
class EnabledRule[R: Rule]:
    """A rule a run enables, with the severity its occurrences are reported at.

    Attributes:
        rule: The rule class, whose `check` the runner calls on the context or the input its partition reads.
        severity: The severity each of the rule's occurrences is reported at.
    """

    rule: type[R]
    severity: Severity


class RuleTable:
    """The enabled rules of one run, each with its severity, partitioned by base in code order."""

    _document_rules: tuple[EnabledRule[DocumentRule], ...]
    _document_rules_by_facet: dict[Facet, tuple[EnabledRule[DocumentRule], ...]]
    _skill_rules: tuple[EnabledRule[SkillRule], ...]
    # One partition per input kind, until the rules that read one read a context.
    _token_count_rules: tuple[EnabledRule[TokenCountRule], ...]
    _line_count_rules: tuple[EnabledRule[LineCountRule], ...]
    _frontmatter_block_rules: tuple[EnabledRule[FrontmatterBlockRule], ...]
    _schema_problems_rules: tuple[EnabledRule[SchemaProblemsRule], ...]
    _headings_rules: tuple[EnabledRule[HeadingsRule], ...]
    _outline_divergence_rules: tuple[EnabledRule[OutlineDivergenceRule], ...]

    def __init__(self, severities: Mapping[type[Rule], Severity]) -> None:
        """Hold the enabled rules, and partition them by the base each derives from.

        Args:
            severities: Each enabled rule, mapped to the severity its occurrences are reported at; a rule absent
                from it does not run.

        Raises:
            UnknownRuleInputError: If a rule derives from no base the table partitions by.
        """
        document_rules: list[EnabledRule[DocumentRule]] = []
        skill_rules: list[EnabledRule[SkillRule]] = []
        token_count_rules: list[EnabledRule[TokenCountRule]] = []
        line_count_rules: list[EnabledRule[LineCountRule]] = []
        frontmatter_block_rules: list[EnabledRule[FrontmatterBlockRule]] = []
        schema_problems_rules: list[EnabledRule[SchemaProblemsRule]] = []
        headings_rules: list[EnabledRule[HeadingsRule]] = []
        outline_divergence_rules: list[EnabledRule[OutlineDivergenceRule]] = []
        for rule_class in sorted(severities, key=_printed_code):
            # The rule hierarchy is open, so the chain cannot close with `assert_never`: a rule over a base with no
            # partition here is a defect, raised before any subject is checked.
            if issubclass(rule_class, DocumentRule):
                document_rules.append(EnabledRule(rule_class, severities[rule_class]))
            elif issubclass(rule_class, SkillRule):
                skill_rules.append(EnabledRule(rule_class, severities[rule_class]))
            elif issubclass(rule_class, TokenCountRule):
                token_count_rules.append(EnabledRule(rule_class, severities[rule_class]))
            elif issubclass(rule_class, LineCountRule):
                line_count_rules.append(EnabledRule(rule_class, severities[rule_class]))
            elif issubclass(rule_class, FrontmatterBlockRule):
                frontmatter_block_rules.append(EnabledRule(rule_class, severities[rule_class]))
            elif issubclass(rule_class, SchemaProblemsRule):
                schema_problems_rules.append(EnabledRule(rule_class, severities[rule_class]))
            elif issubclass(rule_class, HeadingsRule):
                headings_rules.append(EnabledRule(rule_class, severities[rule_class]))
            elif issubclass(rule_class, OutlineDivergenceRule):
                outline_divergence_rules.append(EnabledRule(rule_class, severities[rule_class]))
            else:
                raise UnknownRuleInputError(rule_class)
        self._document_rules = tuple(document_rules)
        self._document_rules_by_facet = {}
        for facet in Facet:
            self._document_rules_by_facet[facet] = tuple(
                enabled for enabled in document_rules if enabled.rule.GOVERNED_BY is facet
            )
        self._skill_rules = tuple(skill_rules)
        self._token_count_rules = tuple(token_count_rules)
        self._line_count_rules = tuple(line_count_rules)
        self._frontmatter_block_rules = tuple(frontmatter_block_rules)
        self._schema_problems_rules = tuple(schema_problems_rules)
        self._headings_rules = tuple(headings_rules)
        self._outline_divergence_rules = tuple(outline_divergence_rules)

    @classmethod
    def from_registry(cls, registry: Registry) -> Self:
        """Enable every rule of a registry at its default level, with no configuration and no selection.

        Args:
            registry: The rules the run may enable; its removed rules and engine conditions are left out.

        Raises:
            UnknownRuleInputError: If an enabled rule derives from no base the table partitions by.
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
    def token_count_rules(self) -> tuple[EnabledRule[TokenCountRule], ...]:
        """Each enabled rule over a document's token count, with its severity, in code order; empty when none is."""
        return self._token_count_rules

    @property
    def line_count_rules(self) -> tuple[EnabledRule[LineCountRule], ...]:
        """Each enabled rule over a skill's line count, with its severity, in code order; empty when none is."""
        return self._line_count_rules

    @property
    def frontmatter_block_rules(self) -> tuple[EnabledRule[FrontmatterBlockRule], ...]:
        """Each enabled rule over a frontmatter block, with its severity, in code order; empty when none is."""
        return self._frontmatter_block_rules

    @property
    def schema_problems_rules(self) -> tuple[EnabledRule[SchemaProblemsRule], ...]:
        """Each enabled rule over the schema problems, with its severity, in code order; empty when none is."""
        return self._schema_problems_rules

    @property
    def headings_rules(self) -> tuple[EnabledRule[HeadingsRule], ...]:
        """Each enabled rule over a document's headings, with its severity, in code order; empty when none is."""
        return self._headings_rules

    @property
    def outline_divergence_rules(self) -> tuple[EnabledRule[OutlineDivergenceRule], ...]:
        """Each enabled rule over the outline divergences, with its severity, in code order; empty when none is."""
        return self._outline_divergence_rules


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
