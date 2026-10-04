"""The registry: a walk of a rules package, its rejections, and a lookup by code, name or alias code."""

import pytest

from ..registry import (
    DuplicateAliasCodeError,
    DuplicateRuleCodeError,
    DuplicateRuleNameError,
    Registry,
    package_registry,
)
from .sample_rules import (
    alias_as_code,
    duplicate_alias,
    duplicate_code,
    duplicate_name,
    import_failure,
)
from .sample_rules import valid as valid_rules
from .sample_rules.alias_as_code.aliased import Lookalike, Original
from .sample_rules.duplicate_alias.aliased import FirstAliased, SecondAliased
from .sample_rules.duplicate_code.first import FirstRule
from .sample_rules.duplicate_code.second import SecondRule
from .sample_rules.duplicate_name.shared import InService, Retired
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
        assert exc_info.value.name == 'shared-name', 'the error names the name bound twice'
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
    def test_package_registry_with_no_rule_declared_holds_none(self) -> None:
        #: Given
        expected: tuple[()] = ()

        #: When
        loaded = package_registry()

        #: Then
        assert loaded.rules == expected, '`lorecraft.rules` declares no rule yet'

    def test_package_registry_with_sample_rules_declared_holds_none_of_them(self) -> None:
        #: Given
        sample_rules = {UppercaseEntry, EmptyLine, TrailingSpace, TabIndent}

        #: When
        loaded = package_registry()

        #: Then
        assert sample_rules.isdisjoint(loaded.rules), (
            'the sample rules lie in the unit tests of `lorecraft.rules`, which its own registry leaves out'
        )

    def test_package_registry_called_twice_returns_the_same_registry(self) -> None:
        #: Given
        first = package_registry()

        #: When
        second = package_registry()

        #: Then
        assert second is first, 'the registry is built once per process'
