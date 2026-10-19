"""The item gates a rule declares alongside its existing item-kind bases."""

from types import MappingProxyType

import pytest

from lorecraft import rules
from lorecraft.project.item import ItemKind
from lorecraft.rules.frontmatter.duplicate_key import DuplicateKey
from lorecraft.rules.frontmatter.name_mismatch import NameMismatch
from lorecraft.rules.length.too_many_lines import TooManyLines
from lorecraft.rules.length.too_many_tokens import TooManyTokens
from lorecraft.rules.link.broken_link import BrokenLink
from lorecraft.rules.registry import Registry
from lorecraft.rules.subject import ByMetaSpec, ByPackage, BySchema, ItemRule, MetaSpecPart
from lorecraft.schemas.builtin import AGENT_SKILLS_SCHEMA_REFERENCE


@pytest.mark.unit
class TestGates:
    def test_registered_item_rules_with_known_kinds_have_gates(self) -> None:
        #: Given
        registered_rules = Registry.load(rules).rules

        #: When
        item_rules = tuple(rule for rule in registered_rules if issubclass(rule, ItemRule))

        #: Then
        assert item_rules, 'the registry includes rules over items'
        assert all(rule.GATES for rule in item_rules), 'each registered item rule declares at least one gate'
        assert all(set(rule.GATES) <= set(ItemKind) for rule in item_rules), 'each gate names a known item kind'

    def test_document_rule_with_budget_part_uses_meta_spec_gate(self) -> None:
        #: Given
        rule = TooManyTokens
        expected = ByMetaSpec(MetaSpecPart.BUDGET)

        #: When
        gate = rule.GATES[ItemKind.DOCUMENT]

        #: Then
        assert gate == expected, 'the document budget rule requires its declared meta spec part'

    def test_document_and_skill_rule_with_budget_part_uses_both_meta_spec_gates(self) -> None:
        #: Given
        rule = TooManyTokens
        expected = MappingProxyType(
            {
                ItemKind.DOCUMENT: ByMetaSpec(MetaSpecPart.BUDGET),
                ItemKind.SKILL_ENTRY: ByMetaSpec(MetaSpecPart.BUDGET, requires_loaded_layer=True),
            }
        )

        #: When
        gates = rule.GATES

        #: Then
        assert gates == expected, 'the shared budget rule requires its meta spec part and loaded layer for skills'

    def test_markdown_rule_with_item_kinds_uses_spec_and_package_gates(self) -> None:
        #: Given
        rule = BrokenLink
        expected = MappingProxyType(
            {
                ItemKind.DOCUMENT: ByMetaSpec(MetaSpecPart.STRUCTURE),
                ItemKind.META_SPEC: ByMetaSpec(MetaSpecPart.STRUCTURE),
                ItemKind.SKILL_ENTRY: ByPackage(),
                ItemKind.SKILL_RESOURCE: ByPackage(),
            }
        )

        #: When
        gates = rule.GATES

        #: Then
        assert gates == expected, 'Markdown rules use structure for corpus items and package gates for skill files'

    def test_frontmatter_rule_with_skill_entry_uses_frontmatter_part(self) -> None:
        #: Given
        rule = DuplicateKey
        expected = ByMetaSpec(MetaSpecPart.FRONTMATTER)

        #: When
        gate = rule.GATES[ItemKind.SKILL_ENTRY]

        #: Then
        assert gate == expected, 'skill frontmatter rules follow the active frontmatter meta spec part'

    def test_name_mismatch_with_skill_entry_uses_agent_skills_schema(self) -> None:
        #: Given
        rule = NameMismatch
        expected = BySchema(AGENT_SKILLS_SCHEMA_REFERENCE)

        #: When
        gate = rule.GATES[ItemKind.SKILL_ENTRY]

        #: Then
        assert gate == expected, 'the skill name rule requires the registered Agent Skills schema'


@pytest.mark.unit
class TestGateApplicability:
    def test_registered_item_rules_with_known_kinds_apply_to_items(self) -> None:
        #: Given
        registered_rules = Registry.load(rules).rules

        #: When
        item_rules = tuple(rule for rule in registered_rules if issubclass(rule, ItemRule))

        #: Then
        assert item_rules, 'the registry includes rules over items'
        assert all('GATES' in rule.__dict__ for rule in item_rules), 'each registered item rule declares its own gates'
        assert all(rule.GATES for rule in item_rules), 'each item rule applies to at least one kind'
        assert all(set(rule.GATES) <= set(ItemKind) for rule in item_rules), 'each rule names known item kinds'

    def test_corpus_rule_with_skill_entry_applies_to_skill_entries(self) -> None:
        #: Given
        rule = TooManyTokens
        expected = ItemKind.SKILL_ENTRY

        #: When
        kinds = rule.GATES

        #: Then
        assert expected in kinds, 'corpus rules declare a gate for skill entries as well as documents'

    def test_package_rule_with_skill_entry_applies_to_skill_entries(self) -> None:
        #: Given
        rule = TooManyLines
        expected = ItemKind.SKILL_ENTRY

        #: When
        kinds = rule.GATES

        #: Then
        assert expected in kinds, 'package skill rules declare a gate for skill entries'
