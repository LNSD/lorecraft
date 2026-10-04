"""The rule table: the rules a run enables, each with its severity, and their partition by input kind."""

import pytest

from lorecraft.rules.declaration import Rule, Severity
from lorecraft.rules.length.too_many_tokens import TooManyTokens
from lorecraft.rules.registry import Registry, package_registry
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
        registry = package_registry()

        #: When
        table = RuleTable.from_registry(registry)

        #: Then
        assert table.token_count_rules == (EnabledRule(TooManyTokens, Severity.ERROR),), (
            "the package's token budget is enabled by default as an error, and its engine condition is not in the table"
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
