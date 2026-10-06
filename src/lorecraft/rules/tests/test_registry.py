"""The registry: a walk of a rules package, its rejections, and a lookup by code, name or alias code."""

import pytest

from lorecraft import rules
from lorecraft.rules.engine.invalid_utf8 import InvalidUtf8
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
from lorecraft.rules.length.title_too_long import TitleTooLong
from lorecraft.rules.length.title_too_many_words import TitleTooManyWords
from lorecraft.rules.length.too_many_lines import TooManyLines
from lorecraft.rules.length.too_many_tokens import TooManyTokens
from lorecraft.rules.length.too_many_words import TooManyWords
from lorecraft.rules.link.absolute_link import AbsoluteLink
from lorecraft.rules.outline.empty_section import EmptySection
from lorecraft.rules.outline.extra_title import ExtraTitle
from lorecraft.rules.outline.forbidden_section import ForbiddenSection
from lorecraft.rules.outline.invalid_title import InvalidTitle
from lorecraft.rules.outline.missing_section import MissingSection
from lorecraft.rules.outline.missing_title import MissingTitle
from lorecraft.rules.outline.section_out_of_order import SectionOutOfOrder
from lorecraft.rules.outline.title_not_first import TitleNotFirst
from lorecraft.rules.outline.unexpected_section import UnexpectedSection

from ..declaration import RuleName
from ..registry import (
    AbstractRuleError,
    ConditionOutsideEngineGroupError,
    ConflictingRuleGroupError,
    DuplicateAliasCodeError,
    DuplicateRuleCodeError,
    DuplicateRuleNameError,
    Registry,
    RuleInEngineGroupError,
    UnsetRuleAttributeError,
)
from .sample_rules import (
    abstract_condition,
    abstract_rule,
    alias_as_code,
    condition_outside_engine,
    conflicting_group,
    duplicate_alias,
    duplicate_code,
    duplicate_name,
    import_failure,
    removed_rule_in_engine,
    rule_in_engine,
    token_count,
    unset_attribute,
    unset_condition_attribute,
    unset_facet,
    unset_removed_attribute,
)
from .sample_rules import valid as valid_rules
from .sample_rules.abstract_condition.unworded import Unworded
from .sample_rules.abstract_rule.unchecked import Unchecked
from .sample_rules.alias_as_code.aliased import Lookalike, Original
from .sample_rules.condition_outside_engine.misplaced import Misplaced
from .sample_rules.conflicting_group.retitled import Retitled, Titled
from .sample_rules.duplicate_alias.aliased import FirstAliased, SecondAliased
from .sample_rules.duplicate_code.first import FirstRule
from .sample_rules.duplicate_code.second import SecondRule
from .sample_rules.duplicate_name.shared import InService, Retired
from .sample_rules.removed_rule_in_engine.retired import RetiredTrespasser
from .sample_rules.rule_in_engine.trespassing import Trespassing
from .sample_rules.token_count.any_tokens import AnyTokens
from .sample_rules.token_count.empty_document import EmptyDocument
from .sample_rules.token_count.over_half_budget import OverHalfBudget
from .sample_rules.token_count.retired import NearBudget
from .sample_rules.token_count.sample_condition import SampleCondition
from .sample_rules.unset_attribute.unreleased import Unreleased
from .sample_rules.unset_condition_attribute.unsevere import Unsevere
from .sample_rules.unset_facet.unfaceted import Unfaceted
from .sample_rules.unset_removed_attribute.unreplaced import Unreplaced
from .sample_rules.valid.outline.empty_line import EmptyLine
from .sample_rules.valid.retired import TabIndent
from .sample_rules.valid.trailing_space import TrailingSpace
from .sample_rules.valid.uppercase_entry import UppercaseEntry


@pytest.fixture(scope='module')
def registry() -> Registry:
    """The registry of the sample rules package the registry accepts; immutable, so shared by the module."""
    return Registry.load(valid_rules)


@pytest.mark.unit
class TestRegistryLoad:
    def test_load_with_a_valid_package_holds_its_rules_in_code_order(self) -> None:
        #: Given
        package = valid_rules

        #: When
        loaded = Registry.load(package)

        #: Then
        assert loaded.rules == (UppercaseEntry, EmptyLine, TrailingSpace, TabIndent), (
            'every rule of the package and its subpackage, the removed one included, is held in code order'
        )

    def test_load_with_another_rules_package_imported_holds_only_its_own_rules(self) -> None:
        #: Given
        # FirstRule, declared in another sample package, was imported, and so registered, with this module
        package = valid_rules

        #: When
        loaded = Registry.load(package)

        #: Then
        assert FirstRule not in loaded.rules, 'a rule declared in another package is left out'

    def test_load_with_two_rules_sharing_a_code_raises_duplicate_rule_code_error(self) -> None:
        #: Given
        package = duplicate_code

        #: When
        with pytest.raises(DuplicateRuleCodeError) as exc_info:
            Registry.load(package)

        #: Then
        assert exc_info.value.code == 'SMP001', 'the error names the code bound twice'
        assert {exc_info.value.first, exc_info.value.second} == {FirstRule, SecondRule}, (
            'the error names both rules that declare the code'
        )

    def test_load_with_a_rule_and_a_removed_rule_sharing_a_name_raises_duplicate_rule_name_error(self) -> None:
        #: Given
        package = duplicate_name

        #: When
        with pytest.raises(DuplicateRuleNameError) as exc_info:
            Registry.load(package)

        #: Then
        assert exc_info.value.name == RuleName('shared-name'), 'the error names the name bound twice'
        assert exc_info.value.first is InService, 'the rule earlier in code order bound the name first'
        assert exc_info.value.second is Retired, 'the removed rule bound it again'

    def test_load_with_two_rules_sharing_an_alias_code_raises_duplicate_alias_code_error(self) -> None:
        #: Given
        package = duplicate_alias

        #: When
        with pytest.raises(DuplicateAliasCodeError) as exc_info:
            Registry.load(package)

        #: Then
        assert exc_info.value.code == 'MD009', 'the error names the alias code bound twice'
        assert exc_info.value.first is FirstAliased, 'the rule earlier in code order bound the alias code first'
        assert exc_info.value.second is SecondAliased, 'the later rule bound it again'

    def test_load_with_an_alias_code_spelled_as_a_code_raises_duplicate_alias_code_error(self) -> None:
        #: Given
        package = alias_as_code

        #: When
        with pytest.raises(DuplicateAliasCodeError) as exc_info:
            Registry.load(package)

        #: Then
        assert exc_info.value.code == 'SMP001', 'the error names the alias code that is also a code'
        assert exc_info.value.first is Original, 'the rule with the code holds it'
        assert exc_info.value.second is Lookalike, 'the rule listing it as an alias code bound it again'

    def test_load_with_a_rule_without_check_raises_abstract_rule_error(self) -> None:
        #: Given
        package = abstract_rule

        #: When
        with pytest.raises(AbstractRuleError) as exc_info:
            Registry.load(package)

        #: Then
        assert exc_info.value.declaration is Unchecked, 'the error names the abstract rule class'
        assert exc_info.value.missing == ('check',), 'the error names the method it does not implement'

    def test_load_with_a_rule_without_since_raises_unset_rule_attribute_error(self) -> None:
        #: Given
        package = unset_attribute

        #: When
        with pytest.raises(UnsetRuleAttributeError) as exc_info:
            Registry.load(package)

        #: Then
        assert exc_info.value.declaration is Unreleased, 'the error names the rule missing the attribute'
        assert exc_info.value.attribute == 'SINCE', 'the error names the attribute it leaves unbound'

    def test_load_with_a_removed_rule_without_replaced_by_raises_unset_rule_attribute_error(self) -> None:
        #: Given
        package = unset_removed_attribute

        #: When
        with pytest.raises(UnsetRuleAttributeError) as exc_info:
            Registry.load(package)

        #: Then
        assert exc_info.value.declaration is Unreplaced, 'the error names the removed rule missing the attribute'
        assert exc_info.value.attribute == 'REPLACED_BY', 'the error names the attribute it leaves unbound'

    def test_load_with_a_document_rule_without_a_facet_raises_unset_rule_attribute_error(self) -> None:
        #: Given
        package = unset_facet

        #: When
        with pytest.raises(UnsetRuleAttributeError) as exc_info:
            Registry.load(package)

        #: Then
        assert exc_info.value.declaration is Unfaceted, 'the error names the rule over a document missing its facet'
        assert exc_info.value.attribute == 'GOVERNED_BY', 'the error names the attribute it leaves unbound'

    def test_load_with_one_prefix_given_two_titles_raises_conflicting_rule_group_error(self) -> None:
        #: Given
        package = conflicting_group

        #: When
        with pytest.raises(ConflictingRuleGroupError) as exc_info:
            Registry.load(package)

        #: Then
        assert exc_info.value.prefix == 'SMP', 'the error names the prefix given two groups'
        assert exc_info.value.first is Titled, 'the rule earlier in code order bound the prefix first'
        assert exc_info.value.second is Retitled, 'the later rule gave it another title'

    def test_load_with_an_engine_condition_holds_it_in_code_order(self) -> None:
        #: Given
        package = token_count

        #: When
        loaded = Registry.load(package)

        #: Then
        assert loaded.rules == (SampleCondition, OverHalfBudget, EmptyDocument, AnyTokens, NearBudget), (
            'the engine condition is held beside the rules and the removed rule, in code order'
        )

    def test_load_with_an_engine_condition_without_severity_raises_unset_rule_attribute_error(self) -> None:
        #: Given
        package = unset_condition_attribute

        #: When
        with pytest.raises(UnsetRuleAttributeError) as exc_info:
            Registry.load(package)

        #: Then
        assert exc_info.value.declaration is Unsevere, 'the error names the condition missing the attribute'
        assert exc_info.value.attribute == 'SEVERITY', 'the error names the attribute it leaves unbound'

    def test_load_with_an_engine_condition_without_message_raises_abstract_rule_error(self) -> None:
        #: Given
        package = abstract_condition

        #: When
        with pytest.raises(AbstractRuleError) as exc_info:
            Registry.load(package)

        #: Then
        assert exc_info.value.declaration is Unworded, 'the error names the abstract condition'
        assert exc_info.value.missing == ('message',), 'the error names the method it does not implement'

    def test_load_with_an_engine_condition_outside_the_engine_group_raises_condition_outside_engine_group_error(
        self,
    ) -> None:
        #: Given
        package = condition_outside_engine

        #: When
        with pytest.raises(ConditionOutsideEngineGroupError) as exc_info:
            Registry.load(package)

        #: Then
        assert exc_info.value.declaration is Misplaced, 'the error names the condition outside the engine group'

    def test_load_with_a_rule_in_the_engine_group_raises_rule_in_engine_group_error(self) -> None:
        #: Given
        package = rule_in_engine

        #: When
        with pytest.raises(RuleInEngineGroupError) as exc_info:
            Registry.load(package)

        #: Then
        assert exc_info.value.declaration is Trespassing, 'the error names the rule in the engine group'

    def test_load_with_a_removed_rule_in_the_engine_group_raises_rule_in_engine_group_error(self) -> None:
        #: Given
        package = removed_rule_in_engine

        #: When
        with pytest.raises(RuleInEngineGroupError) as exc_info:
            Registry.load(package)

        #: Then
        assert exc_info.value.declaration is RetiredTrespasser, 'the error names the removed rule in the engine group'

    def test_load_with_a_module_that_fails_to_import_propagates_the_failure(self) -> None:
        #: Given
        package = import_failure

        #: When
        with pytest.raises(ModuleNotFoundError) as exc_info:
            Registry.load(package)

        #: Then
        assert exc_info.value.name == f'{import_failure.__name__}.absent', (
            "the module's own import failure reaches the caller unchanged"
        )


@pytest.mark.unit
class TestRegistryFind:
    def test_find_with_a_code_returns_its_rule(self, registry: Registry) -> None:
        #: Given
        key = 'SMP002'

        #: When
        found = registry.find(key)

        #: Then
        assert found is TrailingSpace, 'a code as printed finds its rule'

    def test_find_with_a_name_returns_its_rule(self, registry: Registry) -> None:
        #: Given
        key = 'trailing-space'

        #: When
        found = registry.find(key)

        #: Then
        assert found is TrailingSpace, 'a name finds its rule'

    def test_find_with_an_alias_code_returns_its_rule(self, registry: Registry) -> None:
        #: Given
        key = 'MD009'

        #: When
        found = registry.find(key)

        #: Then
        assert found is TrailingSpace, 'an alias code finds the rule that lists it'

    def test_find_with_a_removed_code_returns_the_removed_rule(self, registry: Registry) -> None:
        #: Given
        key = 'SMP003'

        #: When
        found = registry.find(key)

        #: Then
        assert found is TabIndent, 'a retired code finds its removed rule'

    def test_find_with_an_unknown_key_returns_none(self, registry: Registry) -> None:
        #: Given
        key = 'SMP999'

        #: When
        found = registry.find(key)

        #: Then
        assert found is None, 'a key no rule has finds nothing'


@pytest.mark.unit
class TestPackageRegistry:
    def test_load_with_the_package_rules_holds_them_in_code_order(self) -> None:
        #: Given
        package = rules

        #: When
        loaded = Registry.load(package)

        #: Then
        assert loaded.rules == (
            MissingFrontmatter,
            InvalidYaml,
            NonMappingFrontmatter,
            NameMismatch,
            DuplicateKey,
            MissingField,
            UnknownField,
            WrongType,
            InvalidValue,
            BlockConstraint,
            InvalidUtf8,
            TooManyTokens,
            TooManyLines,
            TooManyWords,
            TitleTooManyWords,
            TitleTooLong,
            AbsoluteLink,
            MissingTitle,
            ExtraTitle,
            TitleNotFirst,
            EmptySection,
            ForbiddenSection,
            MissingSection,
            SectionOutOfOrder,
            UnexpectedSection,
            InvalidTitle,
        ), 'the registry holds every rule and engine condition `lorecraft.rules` declares, in code order'

    def test_find_with_the_package_rules_and_the_undecodable_condition_code_returns_it(self) -> None:
        #: Given
        package = rules
        registry = Registry.load(package)
        key = 'LC001'

        #: When
        found = registry.find(key)

        #: Then
        assert found is InvalidUtf8, "the engine's own condition is found by its code, as a rule is"

    def test_load_with_sample_rules_declared_holds_none_of_them(self) -> None:
        #: Given
        package = rules
        sample_rules = {UppercaseEntry, EmptyLine, TrailingSpace, TabIndent, SampleCondition}

        #: When
        loaded = Registry.load(package)

        #: Then
        assert sample_rules.isdisjoint(loaded.rules), (
            'the sample rules lie in the unit tests of `lorecraft.rules`, which its own registry leaves out'
        )
