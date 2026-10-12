"""The rule table: the rules a run enables, each with its severity, and their partition by base."""

from typing import Final

import pytest

from lorecraft import rules
from lorecraft.rules.declaration import Rule, RuleCode, Severity
from lorecraft.rules.frontmatter.allowed_tools_too_long import AllowedToolsTooLong
from lorecraft.rules.frontmatter.block_constraint import BlockConstraint
from lorecraft.rules.frontmatter.duplicate_key import DuplicateKey
from lorecraft.rules.frontmatter.invalid_value import InvalidValue
from lorecraft.rules.frontmatter.invalid_yaml import InvalidYaml
from lorecraft.rules.frontmatter.malformed_allowed_tools import MalformedAllowedTools
from lorecraft.rules.frontmatter.missing_field import MissingField
from lorecraft.rules.frontmatter.missing_frontmatter import MissingFrontmatter
from lorecraft.rules.frontmatter.name_mismatch import NameMismatch
from lorecraft.rules.frontmatter.non_mapping_frontmatter import NonMappingFrontmatter
from lorecraft.rules.frontmatter.unknown_field import UnknownField
from lorecraft.rules.frontmatter.wrong_type import WrongType
from lorecraft.rules.layout.outside_symlink import OutsideSymlink
from lorecraft.rules.length.title_too_long import TitleTooLong
from lorecraft.rules.length.title_too_many_words import TitleTooManyWords
from lorecraft.rules.length.too_many_lines import TooManyLines
from lorecraft.rules.length.too_many_tokens import TooManyTokens
from lorecraft.rules.length.too_many_words import TooManyWords
from lorecraft.rules.link.absolute_link import AbsoluteLink
from lorecraft.rules.link.broken_link import BrokenLink
from lorecraft.rules.link.escaping_link import EscapingLink
from lorecraft.rules.link.missing_fragment import MissingFragment
from lorecraft.rules.outline.empty_section import EmptySection
from lorecraft.rules.outline.extra_title import ExtraTitle
from lorecraft.rules.outline.forbidden_section import ForbiddenSection
from lorecraft.rules.outline.invalid_title import InvalidTitle
from lorecraft.rules.outline.missing_section import MissingSection
from lorecraft.rules.outline.missing_title import MissingTitle
from lorecraft.rules.outline.section_out_of_order import SectionOutOfOrder
from lorecraft.rules.outline.title_not_first import TitleNotFirst
from lorecraft.rules.outline.unexpected_section import UnexpectedSection
from lorecraft.rules.registry import Registry
from lorecraft.rules.subject import Facet
from lorecraft.rules.tests.sample_rules import token_count
from lorecraft.rules.tests.sample_rules import valid as valid_rules
from lorecraft.rules.tests.sample_rules.groups import SAMPLE
from lorecraft.rules.tests.sample_rules.token_count.any_tokens import AnyTokens
from lorecraft.rules.tests.sample_rules.token_count.empty_document import EmptyDocument
from lorecraft.rules.tests.sample_rules.token_count.over_half_budget import OverHalfBudget
from lorecraft.rules.tests.sample_rules.valid.uppercase_entry import UppercaseEntry

from ..selection import AllRules, RuleSelection
from ..table import EnabledRule, RuleTable, UnknownRuleBaseError, selected_rules_left_off

EVERY_RULE: Final[RuleSelection] = RuleSelection(select=frozenset({AllRules()}), ignore=frozenset())
"""The selection of a run given neither `--select` nor `--ignore`: every rule is kept."""


@pytest.fixture(scope='module')
def registry() -> Registry:
    """The registry of the sample rules over a document's token count; immutable, so shared by the module."""
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
        table = RuleTable.from_registry(registry, EVERY_RULE)

        #: Then
        assert table.document_rules == enabled, (
            'the rules above allow are enabled, in code order; the removed rule and the condition are not rules'
        )

    def test_from_registry_with_a_rule_at_warn_enables_it_as_a_warning(self) -> None:
        #: Given
        registry = Registry((OverHalfBudget,))

        #: When
        table = RuleTable.from_registry(registry, EVERY_RULE)

        #: Then
        assert table.document_rules == (EnabledRule(OverHalfBudget, Severity.WARNING),), (
            'a rule at warn reports warnings'
        )

    def test_from_registry_with_a_rule_at_deny_enables_it_as_an_error(self) -> None:
        #: Given
        registry = Registry((AnyTokens,))

        #: When
        table = RuleTable.from_registry(registry, EVERY_RULE)

        #: Then
        assert table.document_rules == (EnabledRule(AnyTokens, Severity.ERROR),), 'a rule at deny reports errors'

    def test_from_registry_with_a_rule_at_allow_leaves_it_out(self) -> None:
        #: Given
        registry = Registry((EmptyDocument,))

        #: When
        table = RuleTable.from_registry(registry, EVERY_RULE)

        #: Then
        assert table.document_rules == (), 'a rule at allow is not in the table, so it never runs'

    def test_from_registry_with_a_rule_over_no_known_base_raises_unknown_rule_base_error(self) -> None:
        #: Given
        # the valid sample rules derive from sample bases, which no partition of the table holds
        registry = Registry.load(valid_rules)

        #: When
        with pytest.raises(UnknownRuleBaseError) as exc_info:
            RuleTable.from_registry(registry, EVERY_RULE)

        #: Then
        assert exc_info.value.rule is UppercaseEntry, 'the error names the first enabled rule, in code order'

    def test_from_registry_with_the_package_registry_enables_the_rules_over_a_document_in_code_order(self) -> None:
        #: Given
        registry = Registry.load(rules)

        #: When
        table = RuleTable.from_registry(registry, EVERY_RULE)

        #: Then
        assert table.document_rules == (
            EnabledRule(TooManyTokens, Severity.ERROR),
            EnabledRule(TooManyWords, Severity.ERROR),
            EnabledRule(TitleTooManyWords, Severity.ERROR),
            EnabledRule(TitleTooLong, Severity.ERROR),
            EnabledRule(MissingTitle, Severity.ERROR),
            EnabledRule(ExtraTitle, Severity.ERROR),
            EnabledRule(TitleNotFirst, Severity.ERROR),
            EnabledRule(EmptySection, Severity.ERROR),
            EnabledRule(ForbiddenSection, Severity.ERROR),
            EnabledRule(MissingSection, Severity.ERROR),
            EnabledRule(SectionOutOfOrder, Severity.ERROR),
            EnabledRule(UnexpectedSection, Severity.ERROR),
            EnabledRule(InvalidTitle, Severity.ERROR),
        ), (
            "the package's length and outline rules over a document are enabled by default as errors, in code order, "
            'and its engine condition is not in the table'
        )

    def test_from_registry_with_the_package_registry_enables_the_line_budget(self) -> None:
        #: Given
        registry = Registry.load(rules)

        #: When
        table = RuleTable.from_registry(registry, EVERY_RULE)

        #: Then
        assert table.skill_rules == (
            EnabledRule(MalformedAllowedTools, Severity.WARNING),
            EnabledRule(AllowedToolsTooLong, Severity.WARNING),
            EnabledRule(TooManyLines, Severity.ERROR),
        ), "the package's allowed-tools rules are enabled as warnings, and its line budget as an error"

    def test_from_registry_with_the_package_registry_enables_the_link_rules_in_code_order(self) -> None:
        #: Given
        registry = Registry.load(rules)

        #: When
        table = RuleTable.from_registry(registry, EVERY_RULE)

        #: Then
        assert table.markdown_rules == (
            EnabledRule(AbsoluteLink, Severity.ERROR),
            EnabledRule(MissingFragment, Severity.ERROR),
            EnabledRule(BrokenLink, Severity.ERROR),
        ), "the package's rules over a Markdown file's links are enabled by default as errors, in code order"

    def test_from_registry_with_the_package_registry_enables_the_skill_file_link_rule(self) -> None:
        #: Given
        registry = Registry.load(rules)

        #: When
        table = RuleTable.from_registry(registry, EVERY_RULE)

        #: Then
        assert table.skill_file_rules == (EnabledRule(EscapingLink, Severity.ERROR),), (
            "the package's rule over a skill file's escaping links is enabled by default as an error"
        )

    def test_from_registry_with_the_package_registry_enables_the_frontmatter_rules_in_code_order(self) -> None:
        #: Given
        registry = Registry.load(rules)

        #: When
        table = RuleTable.from_registry(registry, EVERY_RULE)

        #: Then
        assert table.frontmatter_rules == (
            EnabledRule(MissingFrontmatter, Severity.ERROR),
            EnabledRule(InvalidYaml, Severity.ERROR),
            EnabledRule(NonMappingFrontmatter, Severity.ERROR),
            EnabledRule(NameMismatch, Severity.ERROR),
            EnabledRule(DuplicateKey, Severity.ERROR),
            EnabledRule(MissingField, Severity.ERROR),
            EnabledRule(UnknownField, Severity.WARNING),
            EnabledRule(WrongType, Severity.ERROR),
            EnabledRule(InvalidValue, Severity.ERROR),
            EnabledRule(BlockConstraint, Severity.ERROR),
        ), "the package's frontmatter rules are enabled by default at their own level, in code order"

    def test_from_registry_with_the_package_registry_runs_the_rules_over_the_headings_under_the_structure_facet(
        self,
    ) -> None:
        #: Given
        registry = Registry.load(rules)

        #: When
        table = RuleTable.from_registry(registry, EVERY_RULE)

        #: Then
        assert table.document_rules_governed_by(Facet.STRUCTURE) == (
            EnabledRule(TooManyWords, Severity.ERROR),
            EnabledRule(TitleTooManyWords, Severity.ERROR),
            EnabledRule(TitleTooLong, Severity.ERROR),
            EnabledRule(MissingTitle, Severity.ERROR),
            EnabledRule(ExtraTitle, Severity.ERROR),
            EnabledRule(TitleNotFirst, Severity.ERROR),
            EnabledRule(EmptySection, Severity.ERROR),
            EnabledRule(ForbiddenSection, Severity.ERROR),
            EnabledRule(InvalidTitle, Severity.ERROR),
        ), "the package's rules over a document's headings judge every document a structure specification governs"

    def test_from_registry_with_the_package_registry_runs_the_outline_divergence_rules_under_the_outline_facet(
        self,
    ) -> None:
        #: Given
        registry = Registry.load(rules)

        #: When
        table = RuleTable.from_registry(registry, EVERY_RULE)

        #: Then
        assert table.document_rules_governed_by(Facet.OUTLINE) == (
            EnabledRule(MissingSection, Severity.ERROR),
            EnabledRule(SectionOutOfOrder, Severity.ERROR),
            EnabledRule(UnexpectedSection, Severity.ERROR),
        ), "the package's rules over where the sections leave their outline judge only a document an outline governs"

    def test_from_registry_with_the_package_registry_enables_the_layout_rules(self) -> None:
        #: Given
        registry = Registry.load(rules)

        #: When
        table = RuleTable.from_registry(registry, EVERY_RULE)

        #: Then
        assert table.layout_rules == (EnabledRule(OutsideSymlink, Severity.ERROR),), (
            "the package's layout rules are enabled by default as errors"
        )


@pytest.mark.unit
class TestRuleTableFromRegistryWithASelection:
    def test_from_registry_with_a_code_selected_enables_that_rule_alone(self, registry: Registry) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({RuleCode(SAMPLE, 3)}), ignore=frozenset())

        #: When
        table = RuleTable.from_registry(registry, selection)

        #: Then
        assert table.document_rules == (EnabledRule(AnyTokens, Severity.ERROR),), (
            'a selected rule is enabled at its level, and the rules not selected are left out'
        )

    def test_from_registry_with_a_group_selected_and_a_code_ignored_leaves_the_ignored_rule_out(
        self, registry: Registry
    ) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({SAMPLE}), ignore=frozenset({RuleCode(SAMPLE, 1)}))

        #: When
        table = RuleTable.from_registry(registry, selection)

        #: Then
        assert table.document_rules == (EnabledRule(AnyTokens, Severity.ERROR),), (
            'an ignored rule is left out of a selected group'
        )

    def test_from_registry_with_a_code_selected_and_its_group_ignored_enables_that_rule_alone(
        self, registry: Registry
    ) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({RuleCode(SAMPLE, 3)}), ignore=frozenset({SAMPLE}))

        #: When
        table = RuleTable.from_registry(registry, selection)

        #: Then
        assert table.document_rules == (EnabledRule(AnyTokens, Severity.ERROR),), (
            'the code, more specific than the group ignored, keeps its rule, and the group leaves the rest out'
        )

    def test_from_registry_with_a_rule_at_allow_selected_leaves_it_out(self, registry: Registry) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({RuleCode(SAMPLE, 2)}), ignore=frozenset())

        #: When
        table = RuleTable.from_registry(registry, selection)

        #: Then
        assert table.document_rules == (), 'a selection never enables a rule at allow'


@pytest.mark.unit
class TestSelectedRulesLeftOff:
    def test_selected_rules_left_off_with_a_rule_at_allow_selected_by_its_code_returns_it(
        self, registry: Registry
    ) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({RuleCode(SAMPLE, 2), RuleCode(SAMPLE, 3)}), ignore=frozenset())

        #: When
        left_off = selected_rules_left_off(registry, selection)

        #: Then
        assert left_off == (EmptyDocument,), 'the rule at allow named by its code is left off; the one at deny runs'

    def test_selected_rules_left_off_with_a_rule_at_allow_selected_by_its_group_returns_nothing(
        self, registry: Registry
    ) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({SAMPLE}), ignore=frozenset())

        #: When
        left_off = selected_rules_left_off(registry, selection)

        #: Then
        assert left_off == (), 'a group selected names none of its rules, so its rules at allow are not warned of'

    def test_selected_rules_left_off_with_a_rule_at_allow_selected_and_ignored_returns_nothing(
        self, registry: Registry
    ) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({RuleCode(SAMPLE, 2)}), ignore=frozenset({RuleCode(SAMPLE, 2)}))

        #: When
        left_off = selected_rules_left_off(registry, selection)

        #: Then
        assert left_off == (), 'an ignored rule is left out by the ignore, not by its level'

    def test_selected_rules_left_off_with_every_rule_selected_returns_nothing(self, registry: Registry) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({AllRules()}), ignore=frozenset())

        #: When
        left_off = selected_rules_left_off(registry, selection)

        #: Then
        assert left_off == (), 'no --select names no rule'


@pytest.mark.unit
class TestRuleTable:
    def test_rule_table_with_rules_out_of_code_order_partitions_them_in_code_order(self) -> None:
        #: Given
        severities: dict[type[Rule], Severity] = {AnyTokens: Severity.ERROR, OverHalfBudget: Severity.WARNING}

        #: When
        table = RuleTable(severities)

        #: Then
        assert table.document_rules == (
            EnabledRule(OverHalfBudget, Severity.WARNING),
            EnabledRule(AnyTokens, Severity.ERROR),
        ), 'a partition is in code order, whatever is given, each rule with the severity given for it'

    def test_rule_table_with_no_rules_has_an_empty_document_partition(self) -> None:
        #: Given
        severities: dict[type[Rule], Severity] = {}

        #: When
        table = RuleTable(severities)

        #: Then
        assert table.document_rules == (), 'no enabled rule reads a document'

    def test_rule_table_with_no_rules_has_an_empty_skill_partition(self) -> None:
        #: Given
        severities: dict[type[Rule], Severity] = {}

        #: When
        table = RuleTable(severities)

        #: Then
        assert table.skill_rules == (), 'no enabled rule reads a skill'

    def test_rule_table_with_no_rules_has_an_empty_markdown_partition(self) -> None:
        #: Given
        severities: dict[type[Rule], Severity] = {}

        #: When
        table = RuleTable(severities)

        #: Then
        assert table.markdown_rules == (), 'no enabled rule reads a Markdown file'

    def test_rule_table_with_no_rules_has_an_empty_skill_file_partition(self) -> None:
        #: Given
        severities: dict[type[Rule], Severity] = {}

        #: When
        table = RuleTable(severities)

        #: Then
        assert table.skill_file_rules == (), "no enabled rule reads a skill's file"

    def test_document_rules_governed_by_with_the_facet_a_rule_reads_returns_it(self) -> None:
        #: Given
        severities: dict[type[Rule], Severity] = {TooManyTokens: Severity.ERROR}
        table = RuleTable(severities)

        #: When
        governed = table.document_rules_governed_by(Facet.BUDGET)

        #: Then
        assert governed == (EnabledRule(TooManyTokens, Severity.ERROR),), (
            'a rule over a document is run under the facet it declares'
        )

    def test_document_rules_governed_by_with_a_facet_no_rule_reads_returns_nothing(self) -> None:
        #: Given
        severities: dict[type[Rule], Severity] = {TooManyTokens: Severity.ERROR}
        table = RuleTable(severities)

        #: When
        governed = table.document_rules_governed_by(Facet.OUTLINE)

        #: Then
        assert governed == (), 'a rule over a document is run under no facet but the one it declares'

    def test_frontmatter_rules_governed_by_with_the_frontmatter_facet_returns_a_rule_over_the_frontmatter(
        self,
    ) -> None:
        #: Given
        severities: dict[type[Rule], Severity] = {NameMismatch: Severity.WARNING}
        table = RuleTable(severities)

        #: When
        governed = table.frontmatter_rules_governed_by(Facet.FRONTMATTER)

        #: Then
        assert governed == (EnabledRule(NameMismatch, Severity.WARNING),), (
            'a rule over the frontmatter is run over a document under the facet its base declares'
        )

    def test_frontmatter_rules_governed_by_with_another_facet_returns_nothing(self) -> None:
        #: Given
        severities: dict[type[Rule], Severity] = {NameMismatch: Severity.WARNING}
        table = RuleTable(severities)

        #: When
        governed = table.frontmatter_rules_governed_by(Facet.STRUCTURE)

        #: Then
        assert governed == (), 'a rule over the frontmatter is run over a document under no other facet'

    def test_rule_table_with_no_rules_has_an_empty_frontmatter_partition(self) -> None:
        #: Given
        severities: dict[type[Rule], Severity] = {}

        #: When
        table = RuleTable(severities)

        #: Then
        assert table.frontmatter_rules == (), 'no enabled rule reads the frontmatter'

    def test_rule_table_with_a_rule_over_the_frontmatter_partitions_it_with_its_severity(self) -> None:
        #: Given
        severities: dict[type[Rule], Severity] = {NameMismatch: Severity.WARNING, TooManyLines: Severity.ERROR}

        #: When
        table = RuleTable(severities)

        #: Then
        assert table.frontmatter_rules == (EnabledRule(NameMismatch, Severity.WARNING),), (
            'a rule over the frontmatter joins the frontmatter partition, and no other'
        )

    def test_rule_table_with_a_rule_over_a_document_and_one_over_a_skill_partitions_each_by_its_base(self) -> None:
        #: Given
        severities: dict[type[Rule], Severity] = {TooManyTokens: Severity.ERROR, TooManyLines: Severity.WARNING}

        #: When
        table = RuleTable(severities)

        #: Then
        assert table.document_rules == (EnabledRule(TooManyTokens, Severity.ERROR),), (
            'a rule over a document joins the document partition, and no other'
        )
        assert table.skill_rules == (EnabledRule(TooManyLines, Severity.WARNING),), (
            'a rule over a skill joins the skill partition, and no other'
        )

    def test_rule_table_with_a_rule_over_the_frontmatter_leaves_it_out_of_the_document_and_skill_partitions(
        self,
    ) -> None:
        #: Given
        severities: dict[type[Rule], Severity] = {MissingField: Severity.ERROR}

        #: When
        table = RuleTable(severities)

        #: Then
        assert table.document_rules == (), 'a rule over the frontmatter is not a rule over a document'
        assert table.skill_rules == (), 'a rule over the frontmatter is not a rule over a skill'

    def test_document_rules_governed_by_with_rules_over_two_facets_returns_each_under_its_own(self) -> None:
        #: Given
        severities: dict[type[Rule], Severity] = {MissingSection: Severity.WARNING, MissingTitle: Severity.ERROR}
        table = RuleTable(severities)

        #: When
        outline_rules = table.document_rules_governed_by(Facet.OUTLINE)

        #: Then
        assert outline_rules == (EnabledRule(MissingSection, Severity.WARNING),), (
            'a rule over a document is grouped under the facet it declares, and no other'
        )

    def test_rule_table_with_no_rules_has_an_empty_layout_partition(self) -> None:
        #: Given
        severities: dict[type[Rule], Severity] = {}

        #: When
        table = RuleTable(severities)

        #: Then
        assert table.layout_rules == (), 'no enabled rule reads a layout entry'

    def test_rule_table_with_a_rule_over_a_layout_entry_partitions_it_by_its_base(self) -> None:
        #: Given
        severities: dict[type[Rule], Severity] = {OutsideSymlink: Severity.WARNING, TooManyLines: Severity.ERROR}

        #: When
        table = RuleTable(severities)

        #: Then
        assert table.layout_rules == (EnabledRule(OutsideSymlink, Severity.WARNING),), (
            'a rule over a layout entry joins the layout partition, and no other'
        )
