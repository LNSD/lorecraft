"""The item gates each queried item rule declares."""

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
from lorecraft.rules.subject import Always, MetaSpecPart, QueriedItemRule, WhenMetaSpec, WhenSchema
from lorecraft.schemas.builtin import AGENT_SKILLS_SCHEMA_REFERENCE


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
        assert all(set(rule.APPLIES_TO) <= set(ItemKind) for rule in item_rules), 'each gate names a known item kind'

    def test_document_rule_with_budget_part_uses_meta_spec_gate(self) -> None:
        #: Given
        rule = TooManyTokens
        expected = WhenMetaSpec(MetaSpecPart.BUDGET)

        #: When
        gate = rule.APPLIES_TO[ItemKind.DOCUMENT]

        #: Then
        assert gate == expected, 'the document budget rule requires its declared meta spec part'

    def test_document_and_skill_rule_with_budget_part_uses_both_meta_spec_gates(self) -> None:
        #: Given
        rule = TooManyTokens
        expected = MappingProxyType(
            {
                ItemKind.DOCUMENT: WhenMetaSpec(MetaSpecPart.BUDGET),
                ItemKind.SKILL_ENTRYPOINT: WhenMetaSpec(MetaSpecPart.BUDGET),
            }
        )

        #: When
        gates = rule.APPLIES_TO

        #: Then
        assert gates == expected, 'the shared budget rule requires its meta spec part and loaded layer for skills'

    def test_markdown_rule_with_item_kinds_uses_spec_and_always_gates(self) -> None:
        #: Given
        rule = BrokenLink
        expected = MappingProxyType(
            {
                ItemKind.DOCUMENT: WhenMetaSpec(MetaSpecPart.STRUCTURE),
                ItemKind.META_SPEC: Always(),
                ItemKind.SKILL_ENTRYPOINT: Always(),
                ItemKind.SKILL_RESOURCE: Always(),
            }
        )

        #: When
        gates = rule.APPLIES_TO

        #: Then
        assert gates == expected, 'Markdown rules use structure for corpus items and Always gates for skill entrypoints'

    def test_frontmatter_rule_with_skill_entry_uses_frontmatter_part(self) -> None:
        #: Given
        rule = DuplicateKey
        expected = WhenMetaSpec(MetaSpecPart.FRONTMATTER)

        #: When
        gate = rule.APPLIES_TO[ItemKind.SKILL_ENTRYPOINT]

        #: Then
        assert gate == expected, 'skill frontmatter rules follow the active frontmatter meta spec part'

    def test_name_mismatch_with_skill_entry_uses_agent_skills_schema(self) -> None:
        #: Given
        rule = NameMismatch
        expected = WhenSchema(AGENT_SKILLS_SCHEMA_REFERENCE)

        #: When
        gate = rule.APPLIES_TO[ItemKind.SKILL_ENTRYPOINT]

        #: Then
        assert gate == expected, 'the skill name rule requires the registered Agent Skills schema'


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
        assert all(rule.APPLIES_TO for rule in item_rules), 'each item rule applies to at least one kind'
        assert all(set(rule.APPLIES_TO) <= set(ItemKind) for rule in item_rules), 'each rule names known item kinds'

    def test_corpus_rule_with_skill_entry_applies_to_skill_entries(self) -> None:
        #: Given
        rule = TooManyTokens
        expected = ItemKind.SKILL_ENTRYPOINT

        #: When
        kinds = rule.APPLIES_TO

        #: Then
        assert expected in kinds, 'corpus rules declare a gate for skill entrypoints as well as documents'

    def test_always_rule_with_skill_entry_applies_to_skill_entries(self) -> None:
        #: Given
        rule = TooManyLines
        expected = ItemKind.SKILL_ENTRYPOINT

        #: When
        kinds = rule.APPLIES_TO

        #: Then
        assert expected in kinds, 'Always skill rules declare a gate for skill entrypoints'
