"""The rule table: the rules a run enables, each with its severity, and their partition by input kind."""

import pytest

from lorecraft import rules
from lorecraft.rules.declaration import Rule, Severity
from lorecraft.rules.frontmatter.block_constraint import BlockConstraint
from lorecraft.rules.frontmatter.duplicate_key import DuplicateKey
from lorecraft.rules.frontmatter.invalid_value import InvalidValue
from lorecraft.rules.frontmatter.invalid_yaml import InvalidYaml
from lorecraft.rules.frontmatter.missing_field import MissingField
from lorecraft.rules.frontmatter.missing_frontmatter import MissingFrontmatter
from lorecraft.rules.frontmatter.name_mismatch import NameMismatch
from lorecraft.rules.frontmatter.non_mapping_frontmatter import NonMappingFrontmatter
from lorecraft.rules.frontmatter.unknown_field import UnknownField
from lorecraft.rules.frontmatter.wrong_type import WrongType
from lorecraft.rules.length.too_many_lines import TooManyLines
from lorecraft.rules.length.too_many_tokens import TooManyTokens
from lorecraft.rules.length.too_many_words import TooManyWords
from lorecraft.rules.outline.empty_section import EmptySection
from lorecraft.rules.outline.extra_title import ExtraTitle
from lorecraft.rules.outline.forbidden_section import ForbiddenSection
from lorecraft.rules.outline.missing_section import MissingSection
from lorecraft.rules.outline.missing_title import MissingTitle
from lorecraft.rules.outline.title_not_first import TitleNotFirst
from lorecraft.rules.registry import Registry
from lorecraft.rules.tests.sample_rules import token_count
from lorecraft.rules.tests.sample_rules import valid as valid_rules
from lorecraft.rules.tests.sample_rules.token_count.any_tokens import AnyTokens
from lorecraft.rules.tests.sample_rules.token_count.empty_document import EmptyDocument
from lorecraft.rules.tests.sample_rules.token_count.over_half_budget import OverHalfBudget
from lorecraft.rules.tests.sample_rules.valid.uppercase_entry import UppercaseEntry

from ..table import EnabledRule, RuleTable, UnknownRuleInputError


@pytest.fixture(scope='module')
def registry() -> Registry:
    """The registry of the sample rules over the token count; immutable, so shared by the module."""
    return Registry.load(token_count)


@pytest.mark.unit
class TestRuleTableFromRegistry:
    def test_from_registry_with_rules_at_every_level_partitions_the_enabled_ones_in_code_order(
        self, registry: Registry
    ) -> None:
        #: Given
        # the registry holds SMP001 at warn, SMP002 at allow and SMP003 at deny, a removed rule and a condition
        enabled = (EnabledRule(OverHalfBudget, Severity.WARNING), EnabledRule(AnyTokens, Severity.ERROR))

        #: When
        table = RuleTable.from_registry(registry)

        #: Then
        assert table.token_count_rules == enabled, (
            'the rules above allow are enabled, in code order; the removed rule and the condition are not rules'
        )

    def test_from_registry_with_a_rule_at_warn_enables_it_as_a_warning(self) -> None:
        #: Given
        registry = Registry((OverHalfBudget,))

        #: When
        table = RuleTable.from_registry(registry)

        #: Then
        assert table.token_count_rules == (EnabledRule(OverHalfBudget, Severity.WARNING),), (
            'a rule at warn reports warnings'
        )

    def test_from_registry_with_a_rule_at_deny_enables_it_as_an_error(self) -> None:
        #: Given
        registry = Registry((AnyTokens,))

        #: When
        table = RuleTable.from_registry(registry)

        #: Then
        assert table.token_count_rules == (EnabledRule(AnyTokens, Severity.ERROR),), 'a rule at deny reports errors'

    def test_from_registry_with_a_rule_at_allow_leaves_it_out(self) -> None:
        #: Given
        registry = Registry((EmptyDocument,))

        #: When
        table = RuleTable.from_registry(registry)

        #: Then
        assert table.token_count_rules == (), 'a rule at allow is not in the table, so it never runs'

    def test_from_registry_with_a_rule_over_no_known_input_raises_unknown_rule_input_error(self) -> None:
        #: Given
        # the valid sample rules read sample inputs, which no partition of the table holds
        registry = Registry.load(valid_rules)

        #: When
        with pytest.raises(UnknownRuleInputError) as exc_info:
            RuleTable.from_registry(registry)

        #: Then
        assert exc_info.value.rule is UppercaseEntry, 'the error names the first enabled rule, in code order'

    def test_from_registry_with_the_package_registry_enables_the_token_budget(self) -> None:
        #: Given
        registry = Registry.load(rules)

        #: When
        table = RuleTable.from_registry(registry)

        #: Then
        assert table.token_count_rules == (EnabledRule(TooManyTokens, Severity.ERROR),), (
            "the package's token budget is enabled by default as an error, and its engine condition is not in the table"
        )

    def test_from_registry_with_the_package_registry_enables_the_line_budget(self) -> None:
        #: Given
        registry = Registry.load(rules)

        #: When
        table = RuleTable.from_registry(registry)

        #: Then
        assert table.line_count_rules == (EnabledRule(TooManyLines, Severity.ERROR),), (
            "the package's line budget is enabled by default as an error"
        )

    def test_from_registry_with_the_package_registry_enables_the_frontmatter_block_rules_in_code_order(self) -> None:
        #: Given
        registry = Registry.load(rules)

        #: When
        table = RuleTable.from_registry(registry)

        #: Then
        assert table.frontmatter_block_rules == (
            EnabledRule(MissingFrontmatter, Severity.ERROR),
            EnabledRule(InvalidYaml, Severity.ERROR),
            EnabledRule(NonMappingFrontmatter, Severity.ERROR),
            EnabledRule(NameMismatch, Severity.ERROR),
            EnabledRule(DuplicateKey, Severity.ERROR),
        ), "the package's frontmatter block rules are enabled by default as errors, in code order"

    def test_from_registry_with_the_package_registry_enables_the_schema_rules(self) -> None:
        #: Given
        registry = Registry.load(rules)

        #: When
        table = RuleTable.from_registry(registry)

        #: Then
        assert table.schema_problems_rules == (
            EnabledRule(MissingField, Severity.ERROR),
            EnabledRule(UnknownField, Severity.WARNING),
            EnabledRule(WrongType, Severity.ERROR),
            EnabledRule(InvalidValue, Severity.ERROR),
            EnabledRule(BlockConstraint, Severity.ERROR),
        ), "the package's schema rules are enabled by default at their own level, in code order"

    def test_from_registry_with_the_package_registry_enables_the_headings_rules(self) -> None:
        #: Given
        registry = Registry.load(rules)

        #: When
        table = RuleTable.from_registry(registry)

        #: Then
        assert table.headings_rules == (
            EnabledRule(TooManyWords, Severity.ERROR),
            EnabledRule(MissingTitle, Severity.ERROR),
            EnabledRule(ExtraTitle, Severity.ERROR),
            EnabledRule(TitleNotFirst, Severity.ERROR),
            EnabledRule(EmptySection, Severity.ERROR),
            EnabledRule(ForbiddenSection, Severity.ERROR),
        ), "the package's headings rules are enabled by default as errors, in code order"

    def test_from_registry_with_the_package_registry_enables_the_outline_divergence_rules(self) -> None:
        #: Given
        registry = Registry.load(rules)

        #: When
        table = RuleTable.from_registry(registry)

        #: Then
        assert table.outline_divergence_rules == (EnabledRule(MissingSection, Severity.ERROR),), (
            "the package's outline divergence rules are enabled by default as errors"
        )


@pytest.mark.unit
class TestRuleTable:
    def test_rule_table_with_rules_out_of_code_order_partitions_them_in_code_order(self) -> None:
        #: Given
        severities: dict[type[Rule], Severity] = {AnyTokens: Severity.ERROR, OverHalfBudget: Severity.WARNING}

        #: When
        table = RuleTable(severities)

        #: Then
        assert table.token_count_rules == (
            EnabledRule(OverHalfBudget, Severity.WARNING),
            EnabledRule(AnyTokens, Severity.ERROR),
        ), 'a partition is in code order, whatever is given, each rule with the severity given for it'

    def test_rule_table_with_no_rules_has_an_empty_token_count_partition(self) -> None:
        #: Given
        severities: dict[type[Rule], Severity] = {}

        #: When
        table = RuleTable(severities)

        #: Then
        assert table.token_count_rules == (), 'no enabled rule reads the token count'

    def test_rule_table_with_no_rules_has_an_empty_line_count_partition(self) -> None:
        #: Given
        severities: dict[type[Rule], Severity] = {}

        #: When
        table = RuleTable(severities)

        #: Then
        assert table.line_count_rules == (), 'no enabled rule reads the line count'

    def test_rule_table_with_no_rules_has_an_empty_frontmatter_block_partition(self) -> None:
        #: Given
        severities: dict[type[Rule], Severity] = {}

        #: When
        table = RuleTable(severities)

        #: Then
        assert table.frontmatter_block_rules == (), 'no enabled rule reads the frontmatter block'

    def test_rule_table_with_a_rule_over_the_frontmatter_block_partitions_it_with_its_severity(self) -> None:
        #: Given
        severities: dict[type[Rule], Severity] = {NameMismatch: Severity.WARNING, TooManyLines: Severity.ERROR}

        #: When
        table = RuleTable(severities)

        #: Then
        assert table.frontmatter_block_rules == (EnabledRule(NameMismatch, Severity.WARNING),), (
            'a rule joins the partition of the input it reads, and no other'
        )

    def test_rule_table_with_a_rule_over_the_line_count_leaves_it_out_of_the_token_count_partition(self) -> None:
        #: Given
        severities: dict[type[Rule], Severity] = {TooManyLines: Severity.WARNING}

        #: When
        table = RuleTable(severities)

        #: Then
        assert table.token_count_rules == (), 'a rule joins the partition of the input it reads, and no other'

    def test_rule_table_with_no_rules_has_an_empty_schema_problems_partition(self) -> None:
        #: Given
        severities: dict[type[Rule], Severity] = {}

        #: When
        table = RuleTable(severities)

        #: Then
        assert table.schema_problems_rules == (), 'no enabled rule reads what the frontmatter schemas reject'

    def test_rule_table_with_a_rule_over_the_schema_problems_leaves_it_out_of_the_line_count_partition(self) -> None:
        #: Given
        severities: dict[type[Rule], Severity] = {MissingField: Severity.ERROR}

        #: When
        table = RuleTable(severities)

        #: Then
        assert table.line_count_rules == (), 'a rule joins the partition of the input it reads, and no other'

    def test_rule_table_with_no_rules_has_an_empty_headings_partition(self) -> None:
        #: Given
        severities: dict[type[Rule], Severity] = {}

        #: When
        table = RuleTable(severities)

        #: Then
        assert table.headings_rules == (), "no enabled rule reads a document's headings"

    def test_rule_table_with_a_rule_over_the_headings_partitions_it_with_its_severity(self) -> None:
        #: Given
        severities: dict[type[Rule], Severity] = {MissingTitle: Severity.WARNING, TooManyTokens: Severity.ERROR}

        #: When
        table = RuleTable(severities)

        #: Then
        assert table.headings_rules == (EnabledRule(MissingTitle, Severity.WARNING),), (
            'a rule joins the partition of the input it reads, and no other'
        )

    def test_rule_table_with_no_rules_has_an_empty_outline_divergence_partition(self) -> None:
        #: Given
        severities: dict[type[Rule], Severity] = {}

        #: When
        table = RuleTable(severities)

        #: Then
        assert table.outline_divergence_rules == (), 'no enabled rule reads where a document diverges from its outline'

    def test_rule_table_with_a_rule_over_the_outline_divergences_partitions_it_with_its_severity(self) -> None:
        #: Given
        severities: dict[type[Rule], Severity] = {MissingSection: Severity.WARNING, MissingTitle: Severity.ERROR}

        #: When
        table = RuleTable(severities)

        #: Then
        assert table.outline_divergence_rules == (EnabledRule(MissingSection, Severity.WARNING),), (
            'a rule joins the partition of the input it reads, and no other'
        )
