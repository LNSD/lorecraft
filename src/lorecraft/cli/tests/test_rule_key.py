"""Parsing and resolving the typed argument of `lorecraft rule [RULE]`."""

from typing import Final

import pytest

from lorecraft.rules.index import ConditionRow, RemovedRuleRow, RuleIndexRow, RuleRow
from lorecraft.rules.registry import Registry
from lorecraft.rules.tests.sample_rules import valid as valid_rules

from ..rule_key import IndexRuleNotInRegistryError, MalformedRuleKeyError, RuleKey, UnknownRuleKeyError


class SampleIndex:
    """A small rule index: two groups, and a rule with an alias code and a removed rule."""

    RULES: Final[tuple[RuleIndexRow, ...]] = (
        ConditionRow('LC001', 'invalid-utf8', 'error'),
        RuleRow('LC304', 'empty-section', 'deny', ('MD040',)),
        RuleRow('LC306', 'missing-section', 'deny', ()),
        RemovedRuleRow('OUT010', 'retired-rule'),
    )

    def find(self, key: str, /) -> RuleIndexRow | None:
        """The row matching a code, name or alias code."""
        return next(
            (
                row
                for row in self.RULES
                if key in (row.code, row.name) or isinstance(row, RuleRow) and key in row.aliases
            ),
            None,
        )


SAMPLE_INDEX: Final[SampleIndex] = SampleIndex()


@pytest.mark.unit
class TestRuleKeyParse:
    def test_parse_with_a_code_returns_the_key(self) -> None:
        #: Given
        raw = 'LC304'

        #: When
        parsed = RuleKey.parse(raw, SAMPLE_INDEX)

        #: Then
        assert parsed == RuleKey('LC304'), 'a code the index has is a key'

    def test_parse_with_a_name_returns_the_key(self) -> None:
        #: Given
        raw = 'empty-section'

        #: When
        parsed = RuleKey.parse(raw, SAMPLE_INDEX)

        #: Then
        assert parsed == RuleKey('empty-section'), 'a name the index has is a key'

    def test_parse_with_an_alias_code_returns_the_key(self) -> None:
        #: Given
        raw = 'MD040'

        #: When
        parsed = RuleKey.parse(raw, SAMPLE_INDEX)

        #: Then
        assert parsed == RuleKey('MD040'), 'an alias code is a key exactly when a rule declares it'

    def test_parse_with_a_removed_rules_code_returns_the_key(self) -> None:
        #: Given
        raw = 'OUT010'

        #: When
        parsed = RuleKey.parse(raw, SAMPLE_INDEX)

        #: Then
        assert parsed == RuleKey('OUT010'), 'a removed rule has a page, so its code is a key'

    def test_parse_with_an_engine_conditions_code_returns_the_key(self) -> None:
        #: Given
        raw = 'LC001'

        #: When
        parsed = RuleKey.parse(raw, SAMPLE_INDEX)

        #: Then
        assert parsed == RuleKey('LC001'), 'an engine condition has a page, so its code is a key'

    def test_parse_with_a_hyphen_after_the_group_raises_malformed_rule_key_error(self) -> None:
        #: Given
        raw = 'OUT-1'

        #: When
        with pytest.raises(MalformedRuleKeyError) as exc_info:
            RuleKey.parse(raw, SAMPLE_INDEX)

        #: Then
        assert exc_info.value.text == 'OUT-1', 'the error names the key that has no form, as typed'

    def test_parse_with_a_group_prefix_raises_malformed_rule_key_error(self) -> None:
        #: Given
        raw = 'OUT'

        #: When
        with pytest.raises(MalformedRuleKeyError) as exc_info:
            RuleKey.parse(raw, SAMPLE_INDEX)

        #: Then
        assert exc_info.value.text == 'OUT', 'a group prefix names no page'

    def test_parse_with_an_underscored_name_raises_malformed_rule_key_error(self) -> None:
        #: Given
        raw = 'Empty_Section'

        #: When
        with pytest.raises(MalformedRuleKeyError) as exc_info:
            RuleKey.parse(raw, SAMPLE_INDEX)

        #: Then
        assert exc_info.value.text == 'Empty_Section', 'a name is kebab-case'

    def test_parse_with_an_empty_argument_raises_malformed_rule_key_error(self) -> None:
        #: Given
        raw = ''

        #: When
        with pytest.raises(MalformedRuleKeyError) as exc_info:
            RuleKey.parse(raw, SAMPLE_INDEX)

        #: Then
        assert exc_info.value.text == '', 'an empty argument has no form'

    def test_parse_with_a_doubled_hyphen_name_raises_malformed_rule_key_error(self) -> None:
        #: Given
        raw = 'empty--section'

        #: When
        with pytest.raises(MalformedRuleKeyError) as exc_info:
            RuleKey.parse(raw, SAMPLE_INDEX)

        #: Then
        assert exc_info.value.text == 'empty--section', 'a name has no doubled hyphen'

    def test_parse_with_four_digits_raises_malformed_rule_key_error(self) -> None:
        #: Given
        raw = 'OUT1234'

        #: When
        with pytest.raises(MalformedRuleKeyError) as exc_info:
            RuleKey.parse(raw, SAMPLE_INDEX)

        #: Then
        assert exc_info.value.text == 'OUT1234', 'a code ends in three digits'

    def test_parse_with_a_leading_space_raises_malformed_rule_key_error(self) -> None:
        #: Given
        raw = ' LC304'

        #: When
        with pytest.raises(MalformedRuleKeyError) as exc_info:
            RuleKey.parse(raw, SAMPLE_INDEX)

        #: Then
        assert exc_info.value.text == ' LC304', 'the argument is matched as typed, with no whitespace stripped'

    def test_parse_with_a_code_of_a_group_no_rule_has_raises_unknown_rule_key_error(self) -> None:
        #: Given
        raw = 'ZZZ001'

        #: When
        with pytest.raises(UnknownRuleKeyError) as exc_info:
            RuleKey.parse(raw, SAMPLE_INDEX)

        #: Then
        assert exc_info.value.text == 'ZZZ001', 'a well-formed code in no group is unknown'

    def test_parse_with_a_code_no_rule_has_raises_unknown_rule_key_error(self) -> None:
        #: Given
        raw = 'OUT999'

        #: When
        with pytest.raises(UnknownRuleKeyError) as exc_info:
            RuleKey.parse(raw, SAMPLE_INDEX)

        #: Then
        assert exc_info.value.text == 'OUT999', 'a well-formed code no rule has is unknown'

    def test_parse_with_a_name_no_rule_has_raises_unknown_rule_key_error(self) -> None:
        #: Given
        raw = 'no-such-rule'

        #: When
        with pytest.raises(UnknownRuleKeyError) as exc_info:
            RuleKey.parse(raw, SAMPLE_INDEX)

        #: Then
        assert exc_info.value.text == 'no-such-rule', 'a well-formed name no rule has is unknown'

    def test_parse_with_an_alias_code_no_rule_declares_raises_unknown_rule_key_error(self) -> None:
        #: Given
        raw = 'MD999'

        #: When
        with pytest.raises(UnknownRuleKeyError) as exc_info:
            RuleKey.parse(raw, SAMPLE_INDEX)

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
        key = RuleKey('LC304')

        #: When
        with pytest.raises(IndexRuleNotInRegistryError) as exc_info:
            key.to_declaration(registry)

        #: Then
        assert exc_info.value.key == 'LC304', 'a key the index holds and the registry lacks is a stale index'
