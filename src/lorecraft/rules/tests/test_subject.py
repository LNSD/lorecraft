"""The applicability a rule base binds: the kinds of item a rule judges and the facet it reads."""

import pytest

from lorecraft import rules
from lorecraft.project.item import ItemKind
from lorecraft.rules.length.too_many_lines import TooManyLines
from lorecraft.rules.length.too_many_tokens import TooManyTokens
from lorecraft.rules.link.broken_link import BrokenLink
from lorecraft.rules.registry import Registry
from lorecraft.rules.subject import Facet, ItemRule, governing_facet


@pytest.mark.unit
class TestGoverningFacet:
    def test_governing_facet_with_a_rule_over_a_document_returns_the_facet_it_declares(self) -> None:
        #: Given
        rule = TooManyTokens

        #: When
        facet = governing_facet(rule)

        #: Then
        assert facet is Facet.BUDGET, 'a rule over a document reads its GOVERNED_BY'

    def test_governing_facet_with_a_rule_over_a_markdown_file_returns_the_structure_facet(self) -> None:
        #: Given
        rule = BrokenLink

        #: When
        facet = governing_facet(rule)

        #: Then
        assert facet is Facet.STRUCTURE, 'its base fixes the facet it judges a document under'

    def test_governing_facet_with_a_rule_over_a_skill_returns_none(self) -> None:
        #: Given
        rule = TooManyLines

        #: When
        facet = governing_facet(rule)

        #: Then
        assert facet is None, 'the package governs every skill, so no facet gates it'


@pytest.mark.unit
class TestAppliesTo:
    def test_applies_to_with_every_registered_rule_over_an_item_names_known_kinds(self) -> None:
        #: Given
        registered = Registry.load(rules).rules

        #: When
        item_rules = [rule for rule in registered if issubclass(rule, ItemRule)]

        #: Then
        assert item_rules, 'the registry holds rules over an item'
        assert all(rule.APPLIES_TO for rule in item_rules), 'every rule over an item applies to some kind'
        assert all(rule.APPLIES_TO <= frozenset(ItemKind) for rule in item_rules), 'each kind it names is known'

    def test_applies_to_with_a_corpus_rule_includes_skill_entries(self) -> None:
        #: Given
        rule = TooManyTokens

        #: When
        kinds = rule.APPLIES_TO

        #: Then
        assert ItemKind.SKILL_ENTRY in kinds, 'a corpus rule can judge documents and skill entries'
