"""The item gates each queried item rule declares."""

from types import MappingProxyType

import pytest

from lorecraft import rules
from lorecraft.project.item import ItemType
from lorecraft.rules.frontmatter.duplicate_key import DuplicateKey
from lorecraft.rules.frontmatter.name_mismatch import NameMismatch
from lorecraft.rules.length.too_many_lines import TooManyLines
from lorecraft.rules.length.too_many_tokens import TooManyTokens
from lorecraft.rules.link.broken_link import BrokenLink
from lorecraft.rules.registry import Registry
from lorecraft.rules.subject import Always, MetaSpecPart, QueriedItemRule, WhenMetaSpec


@pytest.mark.unit
class TestGates:
    def test_registered_item_rules_with_known_kinds_have_gates(self) -> None:
        #: Given
        registered_rules = Registry.load(rules).rules

        #: When
        item_rules = tuple(rule for rule in registered_rules if issubclass(rule, QueriedItemRule))

        #: Then
        assert item_rules, 'the registry includes rules over items'
        assert all(rule.APPLIES_TO for rule in item_rules), 'each registered item rule declares at least one gate'
        assert all(set(rule.APPLIES_TO) <= set(ItemType) for rule in item_rules), 'each gate names a known item type'

    def test_meta_spec_rule_gate_matches_its_document_gate(self) -> None:
        #: Given
        registered_rules = Registry.load(rules).rules
        document_rules = tuple(
            rule
            for rule in registered_rules
            if issubclass(rule, QueriedItemRule) and ItemType.DOCUMENT in rule.APPLIES_TO
        )

        #: When
        gate_pairs = tuple(
            (rule.APPLIES_TO.get(ItemType.META_SPEC), rule.APPLIES_TO[ItemType.DOCUMENT]) for rule in document_rules
        )

        #: Then
        assert all(meta_gate == document_gate for meta_gate, document_gate in gate_pairs), (
            'each rule judges meta specs under the same gate as documents'
        )

    def test_document_rule_with_budget_part_uses_meta_spec_gate(self) -> None:
        #: Given
        rule = TooManyTokens
        expected = WhenMetaSpec(MetaSpecPart.BUDGET)

        #: When
        gate = rule.APPLIES_TO[ItemType.DOCUMENT]

        #: Then
        assert gate == expected, 'the document budget rule requires its declared meta spec part'

    def test_line_budget_rule_uses_meta_spec_gates_for_skills(self) -> None:
        #: Given
        rule = TooManyLines
        expected = MappingProxyType(
            {
                ItemType.DOCUMENT: WhenMetaSpec(MetaSpecPart.BUDGET),
                ItemType.META_SPEC: WhenMetaSpec(MetaSpecPart.BUDGET),
                ItemType.SKILL_ENTRYPOINT: WhenMetaSpec(MetaSpecPart.BUDGET),
            }
        )

        #: When
        gates = rule.APPLIES_TO

        #: Then
        assert gates == expected, 'the builtin skill line budget is governed through the budget part'

    def test_markdown_rule_with_item_types_uses_spec_and_always_gates(self) -> None:
        #: Given
        rule = BrokenLink
        expected = MappingProxyType(
            {
                ItemType.DOCUMENT: Always(),
                ItemType.META_SPEC: Always(),
                ItemType.SKILL_ENTRYPOINT: Always(),
                ItemType.SKILL_RESOURCE: Always(),
            }
        )

        #: When
        gates = rule.APPLIES_TO

        #: Then
        assert gates == expected, 'link rules use Always gates for every Markdown item type'

    def test_frontmatter_rule_with_skill_entry_uses_frontmatter_part(self) -> None:
        #: Given
        rule = DuplicateKey
        expected = WhenMetaSpec(MetaSpecPart.FRONTMATTER)

        #: When
        gate = rule.APPLIES_TO[ItemType.SKILL_ENTRYPOINT]

        #: Then
        assert gate == expected, 'skill frontmatter rules follow the active frontmatter meta spec part'

    def test_name_mismatch_with_skill_entry_uses_frontmatter_part(self) -> None:
        #: Given
        rule = NameMismatch
        expected = WhenMetaSpec(MetaSpecPart.FRONTMATTER)

        #: When
        gate = rule.APPLIES_TO[ItemType.SKILL_ENTRYPOINT]

        #: Then
        assert gate == expected, 'the skill name rule follows whether its frontmatter is governed'


@pytest.mark.unit
class TestGateApplicability:
    def test_registered_item_rules_with_known_kinds_apply_to_items(self) -> None:
        #: Given
        registered_rules = Registry.load(rules).rules

        #: When
        item_rules = tuple(rule for rule in registered_rules if issubclass(rule, QueriedItemRule))

        #: Then
        assert item_rules, 'the registry includes rules over items'
        assert all('APPLIES_TO' in rule.__dict__ for rule in item_rules), (
            'each registered item rule declares its own gates'
        )
        assert all(rule.APPLIES_TO for rule in item_rules), 'each item rule applies to at least one item type'
        assert all(set(rule.APPLIES_TO) <= set(ItemType) for rule in item_rules), 'each rule names known item types'

    def test_corpus_rule_with_skill_entry_applies_to_skill_entries(self) -> None:
        #: Given
        rule = TooManyTokens
        expected = ItemType.SKILL_ENTRYPOINT

        #: When
        item_types = rule.APPLIES_TO

        #: Then
        assert expected in item_types, 'corpus rules declare a gate for skill entrypoints as well as documents'

    def test_always_rule_with_skill_entry_applies_to_skill_entries(self) -> None:
        #: Given
        rule = TooManyLines
        expected = ItemType.SKILL_ENTRYPOINT

        #: When
        item_types = rule.APPLIES_TO

        #: Then
        assert expected in item_types, 'Always skill rules declare a gate for skill entrypoints'
