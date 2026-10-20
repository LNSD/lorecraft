"""The rule table: enabled rules, their severity and their item-type and meta spec part index."""

from types import MappingProxyType
from typing import Final

import pytest

from lorecraft import rules
from lorecraft.project.item import ItemType
from lorecraft.rules.corpus.reserved_corpus_overlap import ReservedCorpusOverlap
from lorecraft.rules.frontmatter.duplicate_key import DuplicateKey
from lorecraft.rules.frontmatter.name_mismatch import NameMismatch
from lorecraft.rules.layout.escaping_symlink import EscapingSymlink
from lorecraft.rules.length.too_many_lines import TooManyLines
from lorecraft.rules.length.too_many_tokens import TooManyTokens
from lorecraft.rules.outline.missing_section import MissingSection
from lorecraft.rules.outline.missing_title import MissingTitle
from lorecraft.rules.outline.section_out_of_order import SectionOutOfOrder
from lorecraft.rules.outline.unexpected_section import UnexpectedSection

from ..declaration import Rule
from ..identity import RuleCode, Severity
from ..registry import Registry
from ..selection import AllRules, RuleSelection
from ..subject import MetaSpecPart
from ..table import EnabledRule, RuleTable, UnknownRuleBaseError, selected_rules_left_off
from .sample_rules import token_count
from .sample_rules import valid as valid_rules
from .sample_rules.groups import SAMPLE
from .sample_rules.token_count.any_tokens import AnyTokens
from .sample_rules.token_count.empty_document import EmptyDocument
from .sample_rules.token_count.over_half_budget import OverHalfBudget
from .sample_rules.valid.uppercase_entry import UppercaseEntry

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
        assert table.item_rules(ItemType.DOCUMENT, MetaSpecPart.BUDGET) == enabled, (
            'the rules above allow are enabled, in code order; the removed rule and the condition are not rules'
        )

    def test_from_registry_with_a_rule_at_warn_enables_it_as_a_warning(self) -> None:
        #: Given
        registry = Registry((OverHalfBudget,))

        #: When
        table = RuleTable.from_registry(registry, EVERY_RULE)

        #: Then
        assert table.item_rules(ItemType.DOCUMENT, MetaSpecPart.BUDGET) == (
            EnabledRule(OverHalfBudget, Severity.WARNING),
        ), 'a rule at warn reports warnings'

    def test_from_registry_with_a_rule_at_deny_enables_it_as_an_error(self) -> None:
        #: Given
        registry = Registry((AnyTokens,))

        #: When
        table = RuleTable.from_registry(registry, EVERY_RULE)

        #: Then
        assert table.item_rules(ItemType.DOCUMENT, MetaSpecPart.BUDGET) == (EnabledRule(AnyTokens, Severity.ERROR),), (
            'a rule at deny reports errors'
        )

    def test_from_registry_with_a_rule_at_allow_leaves_it_out(self) -> None:
        #: Given
        registry = Registry((EmptyDocument,))

        #: When
        table = RuleTable.from_registry(registry, EVERY_RULE)

        #: Then
        assert table.item_rules(ItemType.DOCUMENT, MetaSpecPart.BUDGET) == (), (
            'a rule at allow is not in the table, so it never runs'
        )

    def test_from_registry_with_a_rule_over_no_known_base_raises_unknown_rule_base_error(self) -> None:
        #: Given
        # the valid sample rules derive from sample bases, which no partition of the table holds
        registry = Registry.load(valid_rules)

        #: When
        with pytest.raises(UnknownRuleBaseError) as exc_info:
            RuleTable.from_registry(registry, EVERY_RULE)

        #: Then
        assert exc_info.value.rule is UppercaseEntry, 'the error names the first enabled rule, in code order'

    def test_from_registry_with_the_package_registry_runs_the_outline_divergence_rules_under_the_outline_part(
        self,
    ) -> None:
        #: Given
        registry = Registry.load(rules)

        #: When
        table = RuleTable.from_registry(registry, EVERY_RULE)

        #: Then
        assert table.item_rules(ItemType.DOCUMENT, MetaSpecPart.OUTLINE) == (
            EnabledRule(MissingSection, Severity.ERROR),
            EnabledRule(SectionOutOfOrder, Severity.ERROR),
            EnabledRule(UnexpectedSection, Severity.ERROR),
        ), "the package's rules over where the sections leave their outline judge only a document an outline governs"

    def test_from_registry_with_the_package_registry_enables_the_corpus_directory_rules_as_warnings(self) -> None:
        #: Given
        registry = Registry.load(rules)

        #: When
        table = RuleTable.from_registry(registry, EVERY_RULE)

        #: Then
        assert table.corpus_directory_rules == (EnabledRule(ReservedCorpusOverlap, Severity.WARNING),), (
            'the overlap rule defaults to a warning and is handed no symlink'
        )

    def test_from_registry_with_the_package_registry_enables_the_layout_rules(self) -> None:
        #: Given
        registry = Registry.load(rules)

        #: When
        table = RuleTable.from_registry(registry, EVERY_RULE)

        #: Then
        assert table.symlink_rules == (EnabledRule(EscapingSymlink, Severity.ERROR),), (
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
        assert table.item_rules(ItemType.DOCUMENT, MetaSpecPart.BUDGET) == (EnabledRule(AnyTokens, Severity.ERROR),), (
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
        assert table.item_rules(ItemType.DOCUMENT, MetaSpecPart.BUDGET) == (EnabledRule(AnyTokens, Severity.ERROR),), (
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
        assert table.item_rules(ItemType.DOCUMENT, MetaSpecPart.BUDGET) == (EnabledRule(AnyTokens, Severity.ERROR),), (
            'the code, more specific than the group ignored, keeps its rule, and the group leaves the rest out'
        )

    def test_from_registry_with_a_rule_at_allow_selected_leaves_it_out(self, registry: Registry) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({RuleCode(SAMPLE, 2)}), ignore=frozenset())

        #: When
        table = RuleTable.from_registry(registry, selection)

        #: Then
        assert table.item_rules(ItemType.DOCUMENT, MetaSpecPart.BUDGET) == (), (
            'a selection never enables a rule at allow'
        )


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
        assert table.item_rules(ItemType.DOCUMENT, MetaSpecPart.BUDGET) == (
            EnabledRule(OverHalfBudget, Severity.WARNING),
            EnabledRule(AnyTokens, Severity.ERROR),
        ), 'a partition is in code order, whatever is given, each rule with the severity given for it'

    def test_item_rules_with_a_document_budget_gate_returns_the_rule(self) -> None:
        #: Given
        severities: dict[type[Rule], Severity] = {TooManyTokens: Severity.ERROR}
        table = RuleTable(severities)

        #: When
        governed = table.item_rules(ItemType.DOCUMENT, MetaSpecPart.BUDGET)

        #: Then
        assert governed == (EnabledRule(TooManyTokens, Severity.ERROR),), (
            'a rule over a document is run under the meta spec part it declares'
        )

    def test_item_rules_with_another_document_part_returns_nothing(self) -> None:
        #: Given
        severities: dict[type[Rule], Severity] = {TooManyTokens: Severity.ERROR}
        table = RuleTable(severities)

        #: When
        governed = table.item_rules(ItemType.DOCUMENT, MetaSpecPart.OUTLINE)

        #: Then
        assert governed == (), 'a rule over a document is run under no meta spec part but the one it declares'

    def test_item_rules_with_a_document_frontmatter_gate_returns_the_rule(
        self,
    ) -> None:
        #: Given
        severities: dict[type[Rule], Severity] = {NameMismatch: Severity.WARNING}
        table = RuleTable(severities)

        #: When
        governed = table.item_rules(ItemType.DOCUMENT, MetaSpecPart.FRONTMATTER)

        #: Then
        assert governed == (EnabledRule(NameMismatch, Severity.WARNING),), (
            'a rule over the frontmatter is run over a document under the meta spec part its base declares'
        )

    def test_item_rules_with_another_frontmatter_part_returns_nothing(self) -> None:
        #: Given
        severities: dict[type[Rule], Severity] = {NameMismatch: Severity.WARNING}
        table = RuleTable(severities)

        #: When
        governed = table.item_rules(ItemType.DOCUMENT, MetaSpecPart.STRUCTURE)

        #: Then
        assert governed == (), 'a rule over the frontmatter is run over a document under no other meta spec part'

    def test_rule_table_with_no_rules_has_an_empty_frontmatter_partition(self) -> None:
        #: Given
        severities: dict[type[Rule], Severity] = {}

        #: When
        table = RuleTable(severities)

        #: Then
        assert table.item_rules(ItemType.DOCUMENT, MetaSpecPart.FRONTMATTER) == (), 'no document rule reads frontmatter'
        assert table.item_rules(ItemType.SKILL_ENTRYPOINT, MetaSpecPart.FRONTMATTER) == (), (
            'no skill rule reads frontmatter'
        )

    def test_item_rules_with_two_parts_indexes_each_gate_separately(self) -> None:
        #: Given
        severities: dict[type[Rule], Severity] = {MissingSection: Severity.WARNING, MissingTitle: Severity.ERROR}
        table = RuleTable(severities)

        #: When
        outline_rules = table.item_rules(ItemType.DOCUMENT, MetaSpecPart.OUTLINE)

        #: Then
        assert outline_rules == (EnabledRule(MissingSection, Severity.WARNING),), (
            'a rule over a document is grouped under the meta spec part it declares, and no other'
        )

    def test_rule_table_with_no_rules_has_an_empty_layout_partition(self) -> None:
        #: Given
        severities: dict[type[Rule], Severity] = {}

        #: When
        table = RuleTable(severities)

        #: Then
        assert table.symlink_rules == (), 'no enabled rule reads a layout entry'

    def test_rule_table_with_a_rule_over_a_layout_entry_partitions_it_by_its_base(self) -> None:
        #: Given
        severities: dict[type[Rule], Severity] = {EscapingSymlink: Severity.WARNING, TooManyLines: Severity.ERROR}

        #: When
        table = RuleTable(severities)

        #: Then
        assert table.symlink_rules == (EnabledRule(EscapingSymlink, Severity.WARNING),), (
            'a rule over a layout entry joins the layout partition, and no other'
        )


@pytest.mark.unit
class TestRuleTableItemIndex:
    def test_registry_indexes_each_item_rule_under_its_declared_gate(self) -> None:
        #: Given
        registry = Registry.load(rules)
        expected = {
            (ItemType.DOCUMENT, None): ('LINK001', 'LINK002', 'LINK003', 'LINK004'),
            (ItemType.DOCUMENT, MetaSpecPart.FRONTMATTER): (
                'FM001',
                'FM002',
                'FM003',
                'FM004',
                'FM005',
                'FM006',
                'FM007',
                'FM008',
                'FM009',
                'FM010',
                'FM013',
                'FM014',
            ),
            (ItemType.DOCUMENT, MetaSpecPart.STRUCTURE): (
                'LEN003',
                'LEN004',
                'LEN005',
                'LINK005',
                'LINK006',
                'LINK007',
                'OUT001',
                'OUT002',
                'OUT003',
                'OUT004',
                'OUT005',
                'OUT009',
            ),
            (ItemType.DOCUMENT, MetaSpecPart.OUTLINE): ('OUT006', 'OUT007', 'OUT008'),
            (ItemType.DOCUMENT, MetaSpecPart.BUDGET): ('LEN001', 'LEN002'),
            (ItemType.SKILL_ENTRYPOINT, None): (
                'FM011',
                'FM012',
                'LEN002',
                'LINK001',
                'LINK002',
                'LINK003',
                'LINK004',
            ),
            (ItemType.SKILL_ENTRYPOINT, MetaSpecPart.FRONTMATTER): (
                'FM001',
                'FM002',
                'FM003',
                'FM004',
                'FM005',
                'FM006',
                'FM007',
                'FM008',
                'FM009',
                'FM010',
                'FM013',
                'FM014',
            ),
            (ItemType.SKILL_ENTRYPOINT, MetaSpecPart.STRUCTURE): (
                'LEN003',
                'LEN004',
                'LEN005',
                'OUT001',
                'OUT002',
                'OUT003',
                'OUT004',
                'OUT005',
                'OUT009',
            ),
            (ItemType.SKILL_ENTRYPOINT, MetaSpecPart.OUTLINE): ('OUT006', 'OUT007', 'OUT008'),
            (ItemType.SKILL_ENTRYPOINT, MetaSpecPart.BUDGET): ('LEN001',),
            (ItemType.SKILL_RESOURCE, None): ('LINK001', 'LINK002', 'LINK003', 'LINK004'),
            (ItemType.META_SPEC, None): ('LINK001', 'LINK002', 'LINK003', 'LINK004'),
            (ItemType.META_SPEC, MetaSpecPart.FRONTMATTER): (
                'FM001',
                'FM002',
                'FM003',
                'FM004',
                'FM005',
                'FM006',
                'FM007',
                'FM008',
                'FM009',
                'FM010',
                'FM013',
                'FM014',
            ),
            (ItemType.META_SPEC, MetaSpecPart.STRUCTURE): (
                'LEN003',
                'LEN004',
                'LEN005',
                'LINK005',
                'LINK006',
                'LINK007',
                'OUT001',
                'OUT002',
                'OUT003',
                'OUT004',
                'OUT005',
                'OUT009',
            ),
            (ItemType.META_SPEC, MetaSpecPart.OUTLINE): ('OUT006', 'OUT007', 'OUT008'),
            (ItemType.META_SPEC, MetaSpecPart.BUDGET): ('LEN001', 'LEN002'),
        }

        #: When
        table = RuleTable.from_registry(registry, EVERY_RULE)

        #: Then
        for (item_type, part), codes in expected.items():
            actual = tuple(str(enabled.rule.CODE) for enabled in table.item_rules(item_type, part))
            assert actual == codes, (
                f'{item_type.value} {part or "always"} index contains its declared rules in code order'
            )

    def test_empty_table_has_no_rules_in_any_item_index(self) -> None:
        #: Given
        table = RuleTable({})

        #: When
        indexes = {
            (item_type, part): table.item_rules(item_type, part)
            for item_type in ItemType
            for part in (None, *MetaSpecPart)
        }

        #: Then
        assert all(not rules for rules in indexes.values()), 'an empty severity map leaves every item gate bucket empty'

    def test_item_rules_with_a_meta_spec_gate_are_indexed_by_kind_and_part(self) -> None:
        #: Given
        severities: dict[type[Rule], Severity] = {TooManyTokens: Severity.ERROR}
        expected = (EnabledRule(TooManyTokens, Severity.ERROR),)

        #: When
        table = RuleTable(severities)

        #: Then
        assert table.item_rules(ItemType.DOCUMENT, MetaSpecPart.BUDGET) == expected, (
            'the document budget gate indexes its rule'
        )
        assert table.item_rules(ItemType.DOCUMENT, MetaSpecPart.OUTLINE) == (), (
            'a different meta spec part has no budget rule'
        )

    def test_name_mismatch_skill_rule_is_indexed_under_frontmatter(self) -> None:
        #: Given
        severities: dict[type[Rule], Severity] = {NameMismatch: Severity.ERROR}
        expected = (EnabledRule(NameMismatch, Severity.ERROR),)

        #: When
        table = RuleTable(severities)

        #: Then
        assert table.item_rules(ItemType.SKILL_ENTRYPOINT, MetaSpecPart.FRONTMATTER) == expected, (
            'the skill name rule uses the frontmatter governance index'
        )

    def test_frontmatter_rule_with_skill_entry_gate_is_indexed_by_frontmatter(self) -> None:
        #: Given
        severities: dict[type[Rule], Severity] = {DuplicateKey: Severity.ERROR}
        expected = (EnabledRule(DuplicateKey, Severity.ERROR),)

        #: When
        table = RuleTable(severities)

        #: Then
        assert table.item_rules(ItemType.SKILL_ENTRYPOINT, MetaSpecPart.FRONTMATTER) == expected, (
            'skill frontmatter rules use the active frontmatter meta spec part'
        )

    def test_item_rule_without_gates_raises_when_table_is_built(self, monkeypatch: pytest.MonkeyPatch) -> None:
        #: Given
        rule = TooManyTokens
        severities: dict[type[Rule], Severity] = {rule: Severity.ERROR}
        monkeypatch.setattr(rule, 'APPLIES_TO', MappingProxyType({}))

        #: When
        with pytest.raises(UnknownRuleBaseError) as exc_info:
            RuleTable(severities)

        #: Then
        assert exc_info.value.rule is rule, 'the table rejects an item rule that declares no gate'
