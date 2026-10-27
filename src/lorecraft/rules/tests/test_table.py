"""The rule table: enabled rules, their severity and their item-type and spec part index."""

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
from ..identity import Level, Severity
from ..level_resolution import (
    AllRules,
    DefaultLevel,
    ElevatedWarning,
    LevelSetting,
    LevelSource,
    OverriddenLevel,
    ResolvedLevels,
    WrittenSelector,
)
from ..registry import Registry
from ..subject import Always, SpecPart, WhenSpec
from ..table import EnabledRule, RuleTable, UnknownRuleBaseError
from .level_helpers import default_level
from .sample_rules import token_count
from .sample_rules import valid as valid_rules
from .sample_rules.token_count.any_tokens import AnyTokens
from .sample_rules.token_count.empty_document import EmptyDocument
from .sample_rules.token_count.over_half_budget import OverHalfBudget
from .sample_rules.valid.uppercase_entry import UppercaseEntry

EMPTY_LEVELS = ResolvedLevels.from_sources(())


@pytest.fixture(scope='module')
def registry() -> Registry:
    """The registry of the sample rules over a document's token count; immutable, so shared by the module."""
    return Registry.load(token_count)


@pytest.mark.unit
class TestRuleTableFromRegistry:
    def test_from_registry_with_an_override_matching_the_default_uses_default_provenance(self) -> None:
        #: Given
        registry = Registry((AnyTokens,))
        settings: LevelSource = {AllRules(): LevelSetting(Level.ALLOW), AnyTokens.CODE: LevelSetting(Level.DENY)}
        levels = ResolvedLevels.from_named_sources((('cli', settings),))

        #: When
        table = RuleTable.from_registry(registry, levels)

        #: Then
        assert table.item_rules(ItemType.DOCUMENT, WhenSpec(SpecPart.BUDGET)) == (
            EnabledRule(AnyTokens, DefaultLevel(default_level(AnyTokens))),
        ), 'an explicit deny equal to the default level does not claim non-default provenance'

    def test_from_registry_with_warning_elevation_has_one_cli_provenance_selector(self) -> None:
        #: Given
        registry = Registry((OverHalfBudget, AnyTokens))

        #: When
        table = RuleTable.from_registry(registry, EMPTY_LEVELS, deny_warnings=True)

        #: Then
        assert table.item_rules(ItemType.DOCUMENT, WhenSpec(SpecPart.BUDGET)) == (
            EnabledRule(OverHalfBudget, ElevatedWarning()),
            EnabledRule(AnyTokens, DefaultLevel(default_level(AnyTokens))),
        ), '`-D warnings` elevates resolved warning rules and leaves default-deny provenance unchanged'

    def test_from_registry_with_warning_elevation_resets_a_default_deny_rule_to_its_default(self) -> None:
        #: Given
        registry = Registry((EscapingSymlink,))
        settings: LevelSource = {EscapingSymlink.CODE: LevelSetting(Level.WARN)}
        levels = ResolvedLevels.from_named_sources((('cli', settings),))

        #: When
        table = RuleTable.from_registry(registry, levels, deny_warnings=True)

        #: Then
        assert table.symlink_rules == (EnabledRule(EscapingSymlink, DefaultLevel(default_level(EscapingSymlink))),), (
            '`-D warnings` restores a default-deny rule after its explicit warn level'
        )

    def test_from_registry_with_alias_override_preserves_the_written_selector(self) -> None:
        #: Given
        registry = Registry((AnyTokens,))
        settings: LevelSource = {AnyTokens.CODE: LevelSetting(Level.WARN, WrittenSelector('MD040'))}
        levels = ResolvedLevels.from_named_sources((('cli', settings),))

        #: When
        table = RuleTable.from_registry(registry, levels)

        #: Then
        assert table.item_rules(ItemType.DOCUMENT, WhenSpec(SpecPart.BUDGET)) == (
            EnabledRule(AnyTokens, OverriddenLevel(Level.WARN, 'cli', WrittenSelector('MD040'))),
        ), 'an alias level note keeps the spelling used by the command line'

    def test_from_registry_with_allow_override_leaves_default_warn_rule_out(self) -> None:
        #: Given
        registry = Registry((OverHalfBudget,))
        settings: LevelSource = {OverHalfBudget.CODE: LevelSetting(Level.ALLOW)}
        levels = ResolvedLevels.from_sources((settings,))

        #: When
        table = RuleTable.from_registry(registry, levels)

        #: Then
        assert table.item_rules(ItemType.DOCUMENT, WhenSpec(SpecPart.BUDGET)) == (), (
            'an allow override removes a rule whose default level is warn'
        )

    def test_from_registry_with_deny_override_reports_default_warn_rule_as_error(self) -> None:
        #: Given
        registry = Registry((OverHalfBudget,))
        settings: LevelSource = {OverHalfBudget.CODE: LevelSetting(Level.DENY)}
        levels = ResolvedLevels.from_sources((settings,))

        #: When
        table = RuleTable.from_registry(registry, levels)

        #: Then
        assert table.item_rules(ItemType.DOCUMENT, WhenSpec(SpecPart.BUDGET)) == (
            EnabledRule(OverHalfBudget, OverriddenLevel(Level.DENY, 'config', OverHalfBudget.CODE)),
        ), 'a deny override changes a default warn rule to error severity'

    def test_from_registry_with_rules_at_every_level_partitions_the_enabled_ones_in_code_order(
        self, registry: Registry
    ) -> None:
        #: Given
        # the registry holds SMP001 at warn, SMP002 at allow and SMP003 at deny, a removed rule and a condition
        enabled = (
            EnabledRule(OverHalfBudget, DefaultLevel(default_level(OverHalfBudget))),
            EnabledRule(AnyTokens, DefaultLevel(default_level(AnyTokens))),
        )

        #: When
        table = RuleTable.from_registry(registry, EMPTY_LEVELS)

        #: Then
        assert table.item_rules(ItemType.DOCUMENT, WhenSpec(SpecPart.BUDGET)) == enabled, (
            'the rules above allow are enabled, in code order; the removed rule and the condition are not rules'
        )

    def test_from_registry_with_a_rule_at_warn_enables_it_as_a_warning(self) -> None:
        #: Given
        registry = Registry((OverHalfBudget,))

        #: When
        table = RuleTable.from_registry(registry, EMPTY_LEVELS)

        #: Then
        assert table.item_rules(ItemType.DOCUMENT, WhenSpec(SpecPart.BUDGET)) == (
            EnabledRule(OverHalfBudget, DefaultLevel(default_level(OverHalfBudget))),
        ), 'a rule at warn reports warnings'

    def test_from_registry_with_a_rule_at_deny_enables_it_as_an_error(self) -> None:
        #: Given
        registry = Registry((AnyTokens,))

        #: When
        table = RuleTable.from_registry(registry, EMPTY_LEVELS)

        #: Then
        assert table.item_rules(ItemType.DOCUMENT, WhenSpec(SpecPart.BUDGET)) == (
            EnabledRule(AnyTokens, DefaultLevel(default_level(AnyTokens))),
        ), 'a rule at deny reports errors'

    def test_from_registry_with_a_rule_at_allow_leaves_it_out(self) -> None:
        #: Given
        registry = Registry((EmptyDocument,))

        #: When
        table = RuleTable.from_registry(registry, EMPTY_LEVELS)

        #: Then
        assert table.item_rules(ItemType.DOCUMENT, WhenSpec(SpecPart.BUDGET)) == (), (
            'a rule at allow is not in the table, so it never runs'
        )

    def test_from_registry_with_a_rule_over_no_known_base_raises_unknown_rule_base_error(self) -> None:
        #: Given
        # the valid sample rules derive from sample bases, which no partition of the table holds
        registry = Registry.load(valid_rules)

        #: When
        with pytest.raises(UnknownRuleBaseError) as exc_info:
            RuleTable.from_registry(registry, EMPTY_LEVELS)

        #: Then
        assert exc_info.value.rule is UppercaseEntry, 'the error names the first enabled rule, in code order'

    def test_from_registry_with_the_package_registry_runs_the_outline_divergence_rules_under_the_outline_part(
        self,
    ) -> None:
        #: Given
        registry = Registry.load(rules)

        #: When
        table = RuleTable.from_registry(registry, EMPTY_LEVELS)

        #: Then
        assert table.item_rules(ItemType.DOCUMENT, WhenSpec(SpecPart.OUTLINE)) == (
            EnabledRule(MissingSection, DefaultLevel(default_level(MissingSection))),
            EnabledRule(SectionOutOfOrder, DefaultLevel(default_level(SectionOutOfOrder))),
            EnabledRule(UnexpectedSection, DefaultLevel(default_level(UnexpectedSection))),
        ), "the package's rules over where the sections leave their outline judge only a document an outline governs"

    def test_from_registry_with_the_package_registry_enables_the_corpus_directory_rules_as_warnings(self) -> None:
        #: Given
        registry = Registry.load(rules)

        #: When
        table = RuleTable.from_registry(registry, EMPTY_LEVELS)

        #: Then
        assert table.corpus_directory_rules == (
            EnabledRule(ReservedCorpusOverlap, DefaultLevel(default_level(ReservedCorpusOverlap))),
        ), 'the overlap rule defaults to a warning and is handed no symlink'

    def test_from_registry_with_the_package_registry_enables_the_layout_rules(self) -> None:
        #: Given
        registry = Registry.load(rules)

        #: When
        table = RuleTable.from_registry(registry, EMPTY_LEVELS)

        #: Then
        assert table.symlink_rules == (EnabledRule(EscapingSymlink, DefaultLevel(default_level(EscapingSymlink))),), (
            "the package's layout rules are enabled by default as errors"
        )


@pytest.mark.unit
class TestRuleTable:
    def test_rule_table_with_rules_out_of_code_order_partitions_them_in_code_order(self) -> None:
        #: Given
        severities: dict[type[Rule], Severity] = {AnyTokens: Severity.ERROR, OverHalfBudget: Severity.WARNING}

        #: When
        table = RuleTable({rule: DefaultLevel(default_level(rule)) for rule in severities})

        #: Then
        assert table.item_rules(ItemType.DOCUMENT, WhenSpec(SpecPart.BUDGET)) == (
            EnabledRule(OverHalfBudget, DefaultLevel(default_level(OverHalfBudget))),
            EnabledRule(AnyTokens, DefaultLevel(default_level(AnyTokens))),
        ), 'a partition is in code order, whatever order the resolved rules were given in'

    def test_item_rules_with_a_document_budget_gate_returns_the_rule(self) -> None:
        #: Given
        severities: dict[type[Rule], Severity] = {TooManyTokens: Severity.ERROR}
        table = RuleTable({rule: DefaultLevel(default_level(rule)) for rule in severities})

        #: When
        governed = table.item_rules(ItemType.DOCUMENT, WhenSpec(SpecPart.BUDGET))

        #: Then
        assert governed == (EnabledRule(TooManyTokens, DefaultLevel(default_level(TooManyTokens))),), (
            'a rule over a document is run under the spec part it declares'
        )

    def test_item_rules_with_another_document_part_returns_nothing(self) -> None:
        #: Given
        severities: dict[type[Rule], Severity] = {TooManyTokens: Severity.ERROR}
        table = RuleTable({rule: DefaultLevel(default_level(rule)) for rule in severities})

        #: When
        governed = table.item_rules(ItemType.DOCUMENT, WhenSpec(SpecPart.OUTLINE))

        #: Then
        assert governed == (), 'a rule over a document is run under no spec part but the one it declares'

    def test_item_rules_with_a_document_frontmatter_gate_returns_the_rule(
        self,
    ) -> None:
        #: Given
        severities: dict[type[Rule], Severity] = {NameMismatch: Severity.WARNING}
        table = RuleTable({rule: DefaultLevel(default_level(rule)) for rule in severities})

        #: When
        governed = table.item_rules(ItemType.DOCUMENT, WhenSpec(SpecPart.FRONTMATTER))

        #: Then
        assert governed == (EnabledRule(NameMismatch, DefaultLevel(default_level(NameMismatch))),), (
            'a rule over the frontmatter is run over a document under the spec part its base declares'
        )

    def test_item_rules_with_another_frontmatter_part_returns_nothing(self) -> None:
        #: Given
        severities: dict[type[Rule], Severity] = {NameMismatch: Severity.WARNING}
        table = RuleTable({rule: DefaultLevel(default_level(rule)) for rule in severities})

        #: When
        governed = table.item_rules(ItemType.DOCUMENT, WhenSpec(SpecPart.STRUCTURE))

        #: Then
        assert governed == (), 'a rule over the frontmatter is run over a document under no other spec part'

    def test_rule_table_with_no_rules_has_an_empty_frontmatter_partition(self) -> None:
        #: Given
        severities: dict[type[Rule], Severity] = {}

        #: When
        table = RuleTable({rule: DefaultLevel(default_level(rule)) for rule in severities})

        #: Then
        assert table.item_rules(ItemType.DOCUMENT, WhenSpec(SpecPart.FRONTMATTER)) == (), (
            'no document rule reads frontmatter'
        )
        assert table.item_rules(ItemType.SKILL_ENTRYPOINT, WhenSpec(SpecPart.FRONTMATTER)) == (), (
            'no skill rule reads frontmatter'
        )

    def test_item_rules_with_two_parts_indexes_each_gate_separately(self) -> None:
        #: Given
        severities: dict[type[Rule], Severity] = {MissingSection: Severity.WARNING, MissingTitle: Severity.ERROR}
        table = RuleTable({rule: DefaultLevel(default_level(rule)) for rule in severities})

        #: When
        outline_rules = table.item_rules(ItemType.DOCUMENT, WhenSpec(SpecPart.OUTLINE))

        #: Then
        assert outline_rules == (EnabledRule(MissingSection, DefaultLevel(default_level(MissingSection))),), (
            'a rule over a document is grouped under the spec part it declares, and no other'
        )

    def test_rule_table_with_no_rules_has_an_empty_layout_partition(self) -> None:
        #: Given
        severities: dict[type[Rule], Severity] = {}

        #: When
        table = RuleTable({rule: DefaultLevel(default_level(rule)) for rule in severities})

        #: Then
        assert table.symlink_rules == (), 'no enabled rule reads a layout entry'

    def test_rule_table_with_a_rule_over_a_layout_entry_partitions_it_by_its_base(self) -> None:
        #: Given
        severities: dict[type[Rule], Severity] = {EscapingSymlink: Severity.WARNING, TooManyLines: Severity.ERROR}

        #: When
        table = RuleTable({rule: DefaultLevel(default_level(rule)) for rule in severities})

        #: Then
        assert table.symlink_rules == (EnabledRule(EscapingSymlink, DefaultLevel(default_level(EscapingSymlink))),), (
            'a rule over a layout entry joins the layout partition, and no other'
        )


@pytest.mark.unit
class TestRuleTableItemIndex:
    def test_registry_indexes_each_item_rule_under_its_declared_gate(self) -> None:
        #: Given
        registry = Registry.load(rules)
        expected = {
            (ItemType.DOCUMENT, Always()): ('LC501', 'LC502', 'LC503', 'LC504'),
            (ItemType.DOCUMENT, WhenSpec(SpecPart.FRONTMATTER)): (
                'LC201',
                'LC202',
                'LC203',
                'LC204',
                'LC205',
                'LC206',
                'LC207',
                'LC208',
                'LC209',
                'LC210',
                'LC213',
                'LC214',
            ),
            (ItemType.DOCUMENT, WhenSpec(SpecPart.STRUCTURE)): (
                'LC301',
                'LC302',
                'LC303',
                'LC304',
                'LC305',
                'LC309',
                'LC403',
                'LC404',
                'LC405',
                'LC505',
                'LC506',
                'LC507',
            ),
            (ItemType.DOCUMENT, WhenSpec(SpecPart.OUTLINE)): ('LC306', 'LC307', 'LC308'),
            (ItemType.DOCUMENT, WhenSpec(SpecPart.BUDGET)): ('LC401', 'LC402'),
            (ItemType.SKILL_ENTRYPOINT, Always()): (
                'LC501',
                'LC502',
                'LC503',
                'LC504',
            ),
            (ItemType.SKILL_ENTRYPOINT, WhenSpec(SpecPart.FRONTMATTER)): (
                'LC201',
                'LC202',
                'LC203',
                'LC204',
                'LC205',
                'LC206',
                'LC207',
                'LC208',
                'LC209',
                'LC210',
                'LC211',
                'LC212',
                'LC213',
                'LC214',
            ),
            (ItemType.SKILL_ENTRYPOINT, WhenSpec(SpecPart.STRUCTURE)): (
                'LC301',
                'LC302',
                'LC303',
                'LC304',
                'LC305',
                'LC309',
                'LC403',
                'LC404',
                'LC405',
            ),
            (ItemType.SKILL_ENTRYPOINT, WhenSpec(SpecPart.OUTLINE)): ('LC306', 'LC307', 'LC308'),
            (ItemType.SKILL_ENTRYPOINT, WhenSpec(SpecPart.BUDGET)): ('LC401', 'LC402'),
            (ItemType.SKILL_RESOURCE, Always()): ('LC501', 'LC502', 'LC503', 'LC504'),
            (ItemType.SPEC, Always()): ('LC501', 'LC502', 'LC503', 'LC504'),
            (ItemType.SPEC, WhenSpec(SpecPart.FRONTMATTER)): (
                'LC201',
                'LC202',
                'LC203',
                'LC204',
                'LC205',
                'LC206',
                'LC207',
                'LC208',
                'LC209',
                'LC210',
                'LC213',
                'LC214',
            ),
            (ItemType.SPEC, WhenSpec(SpecPart.STRUCTURE)): (
                'LC301',
                'LC302',
                'LC303',
                'LC304',
                'LC305',
                'LC309',
                'LC403',
                'LC404',
                'LC405',
                'LC505',
                'LC506',
                'LC507',
            ),
            (ItemType.SPEC, WhenSpec(SpecPart.OUTLINE)): ('LC306', 'LC307', 'LC308'),
            (ItemType.SPEC, WhenSpec(SpecPart.BUDGET)): ('LC401', 'LC402'),
        }

        #: When
        table = RuleTable.from_registry(registry, EMPTY_LEVELS)

        #: Then
        for (item_type, gate), codes in expected.items():
            actual = tuple(str(enabled.rule.CODE) for enabled in table.item_rules(item_type, gate))
            assert actual == codes, f'{item_type.value} {gate!r} index contains its declared rules in code order'

    def test_empty_table_has_no_rules_in_any_item_index(self) -> None:
        #: Given
        table = RuleTable({rule: DefaultLevel(default_level(rule)) for rule in {}})

        #: When
        indexes = {
            (item_type, gate): table.item_rules(item_type, gate)
            for item_type in ItemType
            for gate in (Always(), *(WhenSpec(part) for part in SpecPart))
        }

        #: Then
        assert all(not rules for rules in indexes.values()), (
            'an empty resolution map leaves every item gate bucket empty'
        )

    def test_item_rules_with_a_spec_gate_are_indexed_by_kind_and_part(self) -> None:
        #: Given
        severities: dict[type[Rule], Severity] = {TooManyTokens: Severity.ERROR}
        expected = (EnabledRule(TooManyTokens, DefaultLevel(default_level(TooManyTokens))),)

        #: When
        table = RuleTable({rule: DefaultLevel(default_level(rule)) for rule in severities})

        #: Then
        assert table.item_rules(ItemType.DOCUMENT, WhenSpec(SpecPart.BUDGET)) == expected, (
            'the document budget gate indexes its rule'
        )
        assert table.item_rules(ItemType.DOCUMENT, WhenSpec(SpecPart.OUTLINE)) == (), (
            'a different spec part has no budget rule'
        )

    def test_name_mismatch_skill_rule_is_indexed_under_frontmatter(self) -> None:
        #: Given
        severities: dict[type[Rule], Severity] = {NameMismatch: Severity.ERROR}
        expected = (EnabledRule(NameMismatch, DefaultLevel(default_level(NameMismatch))),)

        #: When
        table = RuleTable({rule: DefaultLevel(default_level(rule)) for rule in severities})

        #: Then
        assert table.item_rules(ItemType.SKILL_ENTRYPOINT, WhenSpec(SpecPart.FRONTMATTER)) == expected, (
            'the skill name rule uses the frontmatter governance index'
        )

    def test_frontmatter_rule_with_skill_entry_gate_is_indexed_by_frontmatter(self) -> None:
        #: Given
        severities: dict[type[Rule], Severity] = {DuplicateKey: Severity.ERROR}
        expected = (EnabledRule(DuplicateKey, DefaultLevel(default_level(DuplicateKey))),)

        #: When
        table = RuleTable({rule: DefaultLevel(default_level(rule)) for rule in severities})

        #: Then
        assert table.item_rules(ItemType.SKILL_ENTRYPOINT, WhenSpec(SpecPart.FRONTMATTER)) == expected, (
            'skill frontmatter rules use the active frontmatter spec part'
        )
