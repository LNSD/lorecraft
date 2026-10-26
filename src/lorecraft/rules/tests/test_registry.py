"""The registry: a walk of a rules package, its rejections, a lookup by code, name or alias code, and one by prefix."""

import sys

import pytest

from lorecraft import rules
from lorecraft.rules.corpus.reserved_corpus_overlap import ReservedCorpusOverlap
from lorecraft.rules.engine.invalid_utf8 import InvalidUtf8
from lorecraft.rules.engine.malformed_structure_file import MalformedStructureFile
from lorecraft.rules.engine.unreadable_path import UnreadablePath
from lorecraft.rules.engine.unusable_structure_file import UnusableStructureFile
from lorecraft.rules.frontmatter.allowed_tools_too_long import AllowedToolsTooLong
from lorecraft.rules.frontmatter.duplicate_key import DuplicateKey
from lorecraft.rules.frontmatter.invalid_frontmatter import InvalidFrontmatter
from lorecraft.rules.frontmatter.invalid_value import InvalidValue
from lorecraft.rules.frontmatter.invalid_yaml import InvalidYaml
from lorecraft.rules.frontmatter.malformed_allowed_tools import MalformedAllowedTools
from lorecraft.rules.frontmatter.missing_field import MissingField
from lorecraft.rules.frontmatter.missing_frontmatter import MissingFrontmatter
from lorecraft.rules.frontmatter.name_mismatch import NameMismatch
from lorecraft.rules.frontmatter.non_mapping_frontmatter import NonMappingFrontmatter
from lorecraft.rules.frontmatter.too_few_fields import TooFewFields
from lorecraft.rules.frontmatter.too_many_fields import TooManyFields
from lorecraft.rules.frontmatter.unknown_field import UnknownField
from lorecraft.rules.frontmatter.wrong_type import WrongType
from lorecraft.rules.layout.escaping_symlink import EscapingSymlink
from lorecraft.rules.length.section_too_many_words import SectionTooManyWords
from lorecraft.rules.length.title_too_long import TitleTooLong
from lorecraft.rules.length.title_too_many_words import TitleTooManyWords
from lorecraft.rules.length.too_many_lines import TooManyLines
from lorecraft.rules.length.too_many_tokens import TooManyTokens
from lorecraft.rules.link.absolute_link import AbsoluteLink
from lorecraft.rules.link.broken_fragment import BrokenFragment
from lorecraft.rules.link.broken_link import BrokenLink
from lorecraft.rules.link.escaping_link import EscapingLink
from lorecraft.rules.link.extension_link import ExtensionLink
from lorecraft.rules.link.missing_base_link import MissingBaseLink
from lorecraft.rules.link.mutual_link import MutualLink
from lorecraft.rules.outline.empty_section import EmptySection
from lorecraft.rules.outline.extra_title import ExtraTitle
from lorecraft.rules.outline.forbidden_section import ForbiddenSection
from lorecraft.rules.outline.invalid_title import InvalidTitle
from lorecraft.rules.outline.missing_section import MissingSection
from lorecraft.rules.outline.missing_title import MissingTitle
from lorecraft.rules.outline.section_out_of_order import SectionOutOfOrder
from lorecraft.rules.outline.title_not_first import TitleNotFirst
from lorecraft.rules.outline.unexpected_section import UnexpectedSection

from ..identity import RuleName
from ..registry import (
    AbstractRuleError,
    DuplicateAliasCodeError,
    DuplicateRuleCodeError,
    DuplicateRuleNameError,
    Registry,
    UnknownReplacementError,
    UnsetRuleAttributeError,
)
from .sample_rules import (
    abstract_condition,
    abstract_rule,
    alias_as_code,
    duplicate_alias,
    duplicate_code,
    duplicate_name,
    import_failure,
    index_named_module,
    token_count,
    unknown_replacement,
    unset_attribute,
    unset_condition_attribute,
    unset_facet,
    unset_removed_attribute,
)
from .sample_rules import valid as valid_rules
from .sample_rules.abstract_condition.unworded import Unworded
from .sample_rules.abstract_rule.unchecked import Unchecked
from .sample_rules.alias_as_code.aliased import Lookalike, Original
from .sample_rules.conflicting_group.retitled import Retitled, Titled
from .sample_rules.duplicate_alias.aliased import FirstAliased, SecondAliased
from .sample_rules.duplicate_code.first import FirstRule
from .sample_rules.duplicate_code.second import SecondRule
from .sample_rules.duplicate_name.shared import InService, Retired
from .sample_rules.index_named_module.group.index import IndexNamed
from .sample_rules.token_count.any_tokens import AnyTokens
from .sample_rules.token_count.empty_document import EmptyDocument
from .sample_rules.token_count.over_half_budget import OverHalfBudget
from .sample_rules.token_count.retired import NearBudget
from .sample_rules.token_count.sample_condition import SampleCondition
from .sample_rules.unknown_replacement.orphaned import Orphaned
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

    def test_load_with_a_rule_without_judge_raises_abstract_rule_error(self) -> None:
        #: Given
        package = abstract_rule

        #: When
        with pytest.raises(AbstractRuleError) as exc_info:
            Registry.load(package)

        #: Then
        assert exc_info.value.declaration is Unchecked, 'the error names the abstract rule class'
        assert exc_info.value.missing == ('judge',), 'the error names the method it does not implement'

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

    def test_load_with_an_item_rule_without_applies_to_raises_unset_rule_attribute_error(self) -> None:
        #: Given
        package = unset_facet

        #: When
        with pytest.raises(UnsetRuleAttributeError) as exc_info:
            Registry.load(package)

        #: Then
        assert exc_info.value.declaration is Unfaceted, 'the error names the item rule missing its applicability'
        assert exc_info.value.attribute == 'APPLIES_TO', 'the error names the unbound applicability declaration'

    def test_registry_with_a_duplicate_code_and_a_conflicting_group_raises_duplicate_rule_code_error(self) -> None:
        #: Given
        # Titled and FirstRule share SMP001, and Retitled gives the prefix SMP another title
        declarations = (Titled, Retitled, FirstRule)

        #: When
        with pytest.raises(DuplicateRuleCodeError) as exc_info:
            Registry(declarations)

        #: Then
        assert exc_info.value.code == 'SMP001', 'a code bound twice is reported before a group given two titles'

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

    def test_load_with_a_removed_rule_replaced_by_an_undeclared_code_raises_unknown_replacement_error(self) -> None:
        #: Given
        package = unknown_replacement

        #: When
        with pytest.raises(UnknownReplacementError) as exc_info:
            Registry.load(package)

        #: Then
        assert exc_info.value.removed_rule is Orphaned, 'the error names the removed rule'
        assert 'SMP002' in str(exc_info.value), 'the message names the code that replaces it'

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
class TestRegistryRulesInService:
    def test_rules_in_service_with_a_removed_rule_and_an_engine_condition_holds_neither(self) -> None:
        #: Given
        registry = Registry.load(token_count)

        #: When
        in_service = registry.rules_in_service

        #: Then
        assert in_service == (OverHalfBudget, EmptyDocument, AnyTokens), (
            'the rules a run may enable, in code order, without the removed rule or the engine condition'
        )


@pytest.mark.unit
class TestPackageRegistry:
    def test_load_with_the_package_rules_holds_them_in_code_order(self) -> None:
        #: Given
        package = rules

        #: When
        loaded = Registry.load(package)

        #: Then
        assert loaded.rules == (
            InvalidUtf8,
            UnreadablePath,
            MalformedStructureFile,
            UnusableStructureFile,
            ReservedCorpusOverlap,
            EscapingSymlink,
            MissingFrontmatter,
            InvalidYaml,
            NonMappingFrontmatter,
            NameMismatch,
            DuplicateKey,
            MissingField,
            UnknownField,
            WrongType,
            InvalidValue,
            InvalidFrontmatter,
            MalformedAllowedTools,
            AllowedToolsTooLong,
            TooManyFields,
            TooFewFields,
            TooManyTokens,
            TooManyLines,
            SectionTooManyWords,
            TitleTooManyWords,
            TitleTooLong,
            AbsoluteLink,
            BrokenFragment,
            BrokenLink,
            EscapingLink,
            ExtensionLink,
            MissingBaseLink,
            MutualLink,
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


@pytest.mark.unit
class TestRegistryLoadWalksAModuleNamedIndex:
    def test_load_with_a_rule_in_a_group_module_named_index_registers_it(self) -> None:
        #: Given
        package = index_named_module

        #: When
        loaded = Registry.load(package)

        #: Then
        assert loaded.rules == (IndexNamed,), 'only the index beside the root is left out, never a rule module'


@pytest.mark.unit
class TestRegistryLoadLeavesTheIndexOut:
    def test_load_with_the_package_rules_imports_none_of_the_rule_index(self, monkeypatch: pytest.MonkeyPatch) -> None:
        #: Given
        package = rules
        for name in [name for name in sys.modules if name.startswith('lorecraft.rules.index')]:
            monkeypatch.delitem(sys.modules, name)

        #: When
        Registry.load(package)

        #: Then
        imported = sorted(name for name in sys.modules if name.startswith('lorecraft.rules.index'))
        assert imported == [], (
            'the index is derived from the registry, so a stale index must not be able to stop it loading'
        )
