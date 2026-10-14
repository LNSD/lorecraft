"""Parsing the values of `--select`, `--ignore` and `rule [RULE]`, and confirming them against the rule index."""

from typing import Final, Literal

import pytest

from lorecraft.rules import index
from lorecraft.rules.registry import Registry
from lorecraft.rules.tests.sample_rules import valid as valid_rules

from ..rule_arguments import (
    AliasSelector,
    AllSelector,
    CodePrefixSelector,
    CodeSelector,
    EmptySelectorError,
    EngineSelectorError,
    GroupSelector,
    IndexRuleNotInRegistryError,
    MalformedRuleKeyError,
    MalformedSelectorError,
    RemovedRuleSelectorError,
    RuleKey,
    RuleNameSelectorError,
    SelectorValue,
    UnknownRuleKeyError,
    UnknownSelectorError,
)

GROUPS: Final[tuple[tuple[str, str], ...]] = (('LC', 'Engine conditions'), ('OUT', 'Outline checks'))
RULES: Final[tuple[tuple[str, str, Literal['rule', 'removed', 'condition'], str, tuple[str, ...]], ...]] = (
    ('LC001', 'invalid-utf8', 'condition', 'error', ()),
    ('OUT004', 'empty-section', 'rule', 'deny', ('MD040',)),
    ('OUT006', 'missing-section', 'rule', 'deny', ()),
    ('OUT010', 'retired-rule', 'removed', '', ()),
)


@pytest.fixture(autouse=True, scope='function')
def rule_index(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace the generated index with a small one: two groups, and a rule with an alias code and a removed rule.

    Args:
        monkeypatch: Swaps the index's `GROUPS` and `RULES` for the test and restores them after.
    """
    monkeypatch.setattr(index, 'GROUPS', GROUPS)
    monkeypatch.setattr(index, 'RULES', RULES)


@pytest.mark.unit
class TestSelectorValueParse:
    def test_parse_with_each_form_parses_the_form(self) -> None:
        #: Given
        raw = 'ALL,OUT,OUT0,OUT00,OUT004,MD040'

        #: When
        parsed = SelectorValue.parse(raw)

        #: Then
        assert parsed == SelectorValue(
            (
                AllSelector(),
                GroupSelector('OUT'),
                CodePrefixSelector('OUT', '0'),
                CodePrefixSelector('OUT', '00'),
                CodeSelector('OUT', 4),
                AliasSelector('MD040', CodeSelector('OUT', 4)),
            )
        ), 'ALL, a group, a code prefix of one and of two digits, a code and an alias code each parse to their form'

    def test_parse_with_whitespace_around_selectors_strips_it(self) -> None:
        #: Given
        raw = ' OUT004 , OUT006'

        #: When
        parsed = SelectorValue.parse(raw)

        #: Then
        assert parsed == SelectorValue((CodeSelector('OUT', 4), CodeSelector('OUT', 6))), (
            'each selector of a value is stripped, in the order typed'
        )

    def test_parse_with_a_trailing_comma_raises_empty_selector_error(self) -> None:
        #: Given
        raw = 'OUT004,'

        #: When
        with pytest.raises(EmptySelectorError) as exc_info:
            SelectorValue.parse(raw)

        #: Then
        assert exc_info.value.value == 'OUT004,', 'the error names the value as typed'

    def test_parse_with_an_empty_value_raises_empty_selector_error(self) -> None:
        #: Given
        raw = ''

        #: When
        with pytest.raises(EmptySelectorError) as exc_info:
            SelectorValue.parse(raw)

        #: Then
        assert exc_info.value.value == '', 'an empty value holds one empty selector, named as typed'

    def test_parse_with_a_lowercase_group_raises_malformed_selector_error(self) -> None:
        #: Given
        raw = 'OUT006,out'

        #: When
        with pytest.raises(MalformedSelectorError) as exc_info:
            SelectorValue.parse(raw)

        #: Then
        assert exc_info.value.text == 'out', 'a group prefix is matched as spelled'

    def test_parse_with_a_hyphen_after_the_group_raises_malformed_selector_error(self) -> None:
        #: Given
        raw = 'OUT-1'

        #: When
        with pytest.raises(MalformedSelectorError) as exc_info:
            SelectorValue.parse(raw)

        #: Then
        assert exc_info.value.text == 'OUT-1', 'a group is followed by digits only'

    def test_parse_with_four_digits_raises_malformed_selector_error(self) -> None:
        #: Given
        raw = 'OUT1234'

        #: When
        with pytest.raises(MalformedSelectorError) as exc_info:
            SelectorValue.parse(raw)

        #: Then
        assert exc_info.value.text == 'OUT1234', 'more digits than a code holds is no code nor prefix'

    def test_parse_with_a_zero_code_raises_malformed_selector_error(self) -> None:
        #: Given
        raw = 'OUT000'

        #: When
        with pytest.raises(MalformedSelectorError) as exc_info:
            SelectorValue.parse(raw)

        #: Then
        assert exc_info.value.text == 'OUT000', 'a code is numbered from 001'

    def test_parse_with_digits_after_all_raises_malformed_selector_error(self) -> None:
        #: Given
        raw = 'ALL1'

        #: When
        with pytest.raises(MalformedSelectorError) as exc_info:
            SelectorValue.parse(raw)

        #: Then
        assert exc_info.value.text == 'ALL1', 'ALL is no group prefix, so it takes no digits'

    def test_parse_with_an_underscored_name_raises_malformed_selector_error(self) -> None:
        #: Given
        raw = 'Empty_Section'

        #: When
        with pytest.raises(MalformedSelectorError) as exc_info:
            SelectorValue.parse(raw)

        #: Then
        assert exc_info.value.text == 'Empty_Section', 'a selector of no form is malformed'

    def test_parse_with_only_digits_raises_malformed_selector_error(self) -> None:
        #: Given
        raw = '123'

        #: When
        with pytest.raises(MalformedSelectorError) as exc_info:
            SelectorValue.parse(raw)

        #: Then
        assert exc_info.value.text == '123', 'digits with no group before them are no selector'

    def test_parse_with_whitespace_inside_a_code_raises_malformed_selector_error(self) -> None:
        #: Given
        raw = 'OUT 004'

        #: When
        with pytest.raises(MalformedSelectorError) as exc_info:
            SelectorValue.parse(raw)

        #: Then
        assert exc_info.value.text == 'OUT 004', 'only the whitespace around a selector is stripped'

    def test_parse_with_a_lowercase_all_raises_malformed_selector_error(self) -> None:
        #: Given
        raw = 'all'

        #: When
        with pytest.raises(MalformedSelectorError) as exc_info:
            SelectorValue.parse(raw)

        #: Then
        assert exc_info.value.text == 'all', 'ALL is matched as spelled'

    def test_parse_with_a_letter_after_the_group_raises_malformed_selector_error(self) -> None:
        #: Given
        raw = 'OUTx'

        #: When
        with pytest.raises(MalformedSelectorError) as exc_info:
            SelectorValue.parse(raw)

        #: Then
        assert exc_info.value.text == 'OUTx', 'a group prefix is uppercase letters only'

    def test_parse_with_a_doubled_hyphen_name_raises_malformed_selector_error(self) -> None:
        #: Given
        raw = 'empty--section'

        #: When
        with pytest.raises(MalformedSelectorError) as exc_info:
            SelectorValue.parse(raw)

        #: Then
        assert exc_info.value.text == 'empty--section', 'a text of no form is malformed, whatever it resembles'

    def test_parse_with_a_code_of_a_group_no_rule_has_raises_unknown_selector_error(self) -> None:
        #: Given
        raw = 'ZZZ004'

        #: When
        with pytest.raises(UnknownSelectorError) as exc_info:
            SelectorValue.parse(raw)

        #: Then
        assert exc_info.value.text == 'ZZZ004', 'a well-formed code in no group is unknown'

    def test_parse_with_a_code_prefix_of_a_group_no_rule_has_raises_unknown_selector_error(self) -> None:
        #: Given
        raw = 'ZZZ0'

        #: When
        with pytest.raises(UnknownSelectorError) as exc_info:
            SelectorValue.parse(raw)

        #: Then
        assert exc_info.value.text == 'ZZZ0', 'a well-formed code prefix of no group is unknown'

    def test_parse_with_a_code_of_a_group_that_no_rule_numbers_raises_unknown_selector_error(self) -> None:
        #: Given
        raw = 'OUT007'

        #: When
        with pytest.raises(UnknownSelectorError) as exc_info:
            SelectorValue.parse(raw)

        #: Then
        assert exc_info.value.text == 'OUT007', 'a well-formed code of a group that has no such number is unknown'

    def test_parse_with_a_code_no_rule_has_raises_unknown_selector_error(self) -> None:
        #: Given
        raw = 'OUT999'

        #: When
        with pytest.raises(UnknownSelectorError) as exc_info:
            SelectorValue.parse(raw)

        #: Then
        assert exc_info.value.text == 'OUT999', 'a well-formed code no rule has is unknown'

    def test_parse_with_a_group_no_rule_has_raises_unknown_selector_error(self) -> None:
        #: Given
        raw = 'ZZZ'

        #: When
        with pytest.raises(UnknownSelectorError) as exc_info:
            SelectorValue.parse(raw)

        #: Then
        assert exc_info.value.text == 'ZZZ', 'a well-formed prefix no group has is unknown'

    def test_parse_with_a_code_prefix_no_rule_starts_raises_unknown_selector_error(self) -> None:
        #: Given
        raw = 'OUT9'

        #: When
        with pytest.raises(UnknownSelectorError) as exc_info:
            SelectorValue.parse(raw)

        #: Then
        assert exc_info.value.text == 'OUT9', 'a code prefix no rule starts is unknown'

    def test_parse_with_a_code_prefix_only_a_removed_rule_starts_raises_unknown_selector_error(self) -> None:
        #: Given
        raw = 'OUT01'

        #: When
        with pytest.raises(UnknownSelectorError) as exc_info:
            SelectorValue.parse(raw)

        #: Then
        assert exc_info.value.text == 'OUT01', 'a code prefix only a removed rule starts is unknown'

    def test_parse_with_an_alias_code_no_rule_declares_raises_unknown_selector_error(self) -> None:
        #: Given
        raw = 'MD999'

        #: When
        with pytest.raises(UnknownSelectorError) as exc_info:
            SelectorValue.parse(raw)

        #: Then
        assert exc_info.value.text == 'MD999', 'an alias code is one exactly when a rule declares it'

    def test_parse_with_a_rule_name_raises_rule_name_selector_error(self) -> None:
        #: Given
        raw = 'empty-section'

        #: When
        with pytest.raises(RuleNameSelectorError) as exc_info:
            SelectorValue.parse(raw)

        #: Then
        assert exc_info.value.code == 'OUT004', 'the error carries the code to write instead'
        assert 'OUT004' in str(exc_info.value), 'the message names the code to write instead'

    def test_parse_with_the_engine_group_raises_engine_selector_error(self) -> None:
        #: Given
        raw = 'LC'

        #: When
        with pytest.raises(EngineSelectorError) as exc_info:
            SelectorValue.parse(raw)

        #: Then
        assert exc_info.value.text == 'LC', "the engine group's prefix cannot be selected"

    def test_parse_with_an_engine_code_prefix_raises_engine_selector_error(self) -> None:
        #: Given
        raw = 'LC9'

        #: When
        with pytest.raises(EngineSelectorError) as exc_info:
            SelectorValue.parse(raw)

        #: Then
        assert exc_info.value.text == 'LC9', 'a prefix of engine condition codes cannot be selected'

    def test_parse_with_an_engine_code_raises_engine_selector_error(self) -> None:
        #: Given
        raw = 'LC001'

        #: When
        with pytest.raises(EngineSelectorError) as exc_info:
            SelectorValue.parse(raw)

        #: Then
        assert exc_info.value.text == 'LC001', "an engine condition's code cannot be selected"

    def test_parse_with_an_engine_name_raises_engine_selector_error(self) -> None:
        #: Given
        raw = 'invalid-utf8'

        #: When
        with pytest.raises(EngineSelectorError) as exc_info:
            SelectorValue.parse(raw)

        #: Then
        assert exc_info.value.text == 'invalid-utf8', "an engine condition's name cannot be selected"

    def test_parse_with_a_removed_code_raises_removed_rule_selector_error(self) -> None:
        #: Given
        raw = 'OUT010'

        #: When
        with pytest.raises(RemovedRuleSelectorError) as exc_info:
            SelectorValue.parse(raw)

        #: Then
        assert exc_info.value.code == 'OUT010', 'the error carries the removed rule code'
        assert 'lorecraft rule OUT010' in str(exc_info.value), 'the message names the command that says more'

    def test_parse_with_a_removed_name_raises_removed_rule_selector_error(self) -> None:
        #: Given
        raw = 'retired-rule'

        #: When
        with pytest.raises(RemovedRuleSelectorError) as exc_info:
            SelectorValue.parse(raw)

        #: Then
        assert exc_info.value.code == 'OUT010', 'a removed rule is refused by its name too, naming its code'


@pytest.mark.unit
class TestSelectorValueStr:
    def test_str_with_each_form_returns_the_values_joined_by_commas(self) -> None:
        #: Given
        value = SelectorValue(
            (
                AllSelector(),
                GroupSelector('OUT'),
                CodePrefixSelector('OUT', '00'),
                CodeSelector('OUT', 4),
                AliasSelector('MD040', CodeSelector('OUT', 4)),
            )
        )

        #: When
        text = str(value)

        #: Then
        assert text == 'ALL,OUT,OUT00,OUT004,MD040', 'each selector prints as typed, a code zero-padded'


@pytest.mark.unit
class TestRuleKeyParse:
    def test_parse_with_a_code_returns_the_key(self) -> None:
        #: Given
        raw = 'OUT004'

        #: When
        parsed = RuleKey.parse(raw)

        #: Then
        assert parsed == RuleKey('OUT004'), 'a code the index has is a key'

    def test_parse_with_a_name_returns_the_key(self) -> None:
        #: Given
        raw = 'empty-section'

        #: When
        parsed = RuleKey.parse(raw)

        #: Then
        assert parsed == RuleKey('empty-section'), 'a name the index has is a key'

    def test_parse_with_an_alias_code_returns_the_key(self) -> None:
        #: Given
        raw = 'MD040'

        #: When
        parsed = RuleKey.parse(raw)

        #: Then
        assert parsed == RuleKey('MD040'), 'an alias code is a key exactly when a rule declares it'

    def test_parse_with_a_removed_rules_code_returns_the_key(self) -> None:
        #: Given
        raw = 'OUT010'

        #: When
        parsed = RuleKey.parse(raw)

        #: Then
        assert parsed == RuleKey('OUT010'), 'a removed rule has a page, so its code is a key'

    def test_parse_with_an_engine_conditions_code_returns_the_key(self) -> None:
        #: Given
        raw = 'LC001'

        #: When
        parsed = RuleKey.parse(raw)

        #: Then
        assert parsed == RuleKey('LC001'), 'an engine condition has a page, so its code is a key'

    def test_parse_with_a_hyphen_after_the_group_raises_malformed_rule_key_error(self) -> None:
        #: Given
        raw = 'OUT-1'

        #: When
        with pytest.raises(MalformedRuleKeyError) as exc_info:
            RuleKey.parse(raw)

        #: Then
        assert exc_info.value.text == 'OUT-1', 'the error names the key that has no form, as typed'

    def test_parse_with_a_group_prefix_raises_malformed_rule_key_error(self) -> None:
        #: Given
        raw = 'OUT'

        #: When
        with pytest.raises(MalformedRuleKeyError) as exc_info:
            RuleKey.parse(raw)

        #: Then
        assert exc_info.value.text == 'OUT', 'a group prefix names no page'

    def test_parse_with_an_underscored_name_raises_malformed_rule_key_error(self) -> None:
        #: Given
        raw = 'Empty_Section'

        #: When
        with pytest.raises(MalformedRuleKeyError) as exc_info:
            RuleKey.parse(raw)

        #: Then
        assert exc_info.value.text == 'Empty_Section', 'a name is kebab-case'

    def test_parse_with_an_empty_argument_raises_malformed_rule_key_error(self) -> None:
        #: Given
        raw = ''

        #: When
        with pytest.raises(MalformedRuleKeyError) as exc_info:
            RuleKey.parse(raw)

        #: Then
        assert exc_info.value.text == '', 'an empty argument has no form'

    def test_parse_with_a_doubled_hyphen_name_raises_malformed_rule_key_error(self) -> None:
        #: Given
        raw = 'empty--section'

        #: When
        with pytest.raises(MalformedRuleKeyError) as exc_info:
            RuleKey.parse(raw)

        #: Then
        assert exc_info.value.text == 'empty--section', 'a name has no doubled hyphen'

    def test_parse_with_four_digits_raises_malformed_rule_key_error(self) -> None:
        #: Given
        raw = 'OUT1234'

        #: When
        with pytest.raises(MalformedRuleKeyError) as exc_info:
            RuleKey.parse(raw)

        #: Then
        assert exc_info.value.text == 'OUT1234', 'a code ends in three digits'

    def test_parse_with_a_leading_space_raises_malformed_rule_key_error(self) -> None:
        #: Given
        raw = ' OUT004'

        #: When
        with pytest.raises(MalformedRuleKeyError) as exc_info:
            RuleKey.parse(raw)

        #: Then
        assert exc_info.value.text == ' OUT004', 'the argument is matched as typed, with no whitespace stripped'

    def test_parse_with_a_code_of_a_group_no_rule_has_raises_unknown_rule_key_error(self) -> None:
        #: Given
        raw = 'ZZZ001'

        #: When
        with pytest.raises(UnknownRuleKeyError) as exc_info:
            RuleKey.parse(raw)

        #: Then
        assert exc_info.value.text == 'ZZZ001', 'a well-formed code in no group is unknown'

    def test_parse_with_a_code_no_rule_has_raises_unknown_rule_key_error(self) -> None:
        #: Given
        raw = 'OUT999'

        #: When
        with pytest.raises(UnknownRuleKeyError) as exc_info:
            RuleKey.parse(raw)

        #: Then
        assert exc_info.value.text == 'OUT999', 'a well-formed code no rule has is unknown'

    def test_parse_with_a_name_no_rule_has_raises_unknown_rule_key_error(self) -> None:
        #: Given
        raw = 'no-such-rule'

        #: When
        with pytest.raises(UnknownRuleKeyError) as exc_info:
            RuleKey.parse(raw)

        #: Then
        assert exc_info.value.text == 'no-such-rule', 'a well-formed name no rule has is unknown'

    def test_parse_with_an_alias_code_no_rule_declares_raises_unknown_rule_key_error(self) -> None:
        #: Given
        raw = 'MD999'

        #: When
        with pytest.raises(UnknownRuleKeyError) as exc_info:
            RuleKey.parse(raw)

        #: Then
        assert exc_info.value.text == 'MD999', 'an alias code is one exactly when a rule declares it'


@pytest.mark.unit
class TestRuleKeyStr:
    def test_str_with_a_key_returns_the_text_as_typed(self) -> None:
        #: Given
        key = RuleKey('empty-section')

        #: When
        text = str(key)

        #: Then
        assert text == 'empty-section', 'a key prints as typed'


@pytest.mark.unit
class TestRuleKeyToDeclaration:
    def test_to_declaration_with_a_code_of_the_registry_returns_the_declaration(self) -> None:
        #: Given
        registry = Registry.load(valid_rules)
        key = RuleKey('SMP002')

        #: When
        declaration = key.to_declaration(registry)

        #: Then
        assert str(declaration.CODE) == 'SMP002', 'the key resolves to the declaration with the code'

    def test_to_declaration_with_a_key_the_registry_lacks_raises_index_rule_not_in_registry_error(self) -> None:
        #: Given
        registry = Registry.load(valid_rules)
        key = RuleKey('OUT004')

        #: When
        with pytest.raises(IndexRuleNotInRegistryError) as exc_info:
            key.to_declaration(registry)

        #: Then
        assert exc_info.value.key == 'OUT004', 'a key the index holds and the registry lacks is a stale index'
