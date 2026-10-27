"""Parsing the values of `--select` and confirming them against the rule index."""

from typing import Final

import pytest

from lorecraft.rules.index import ConditionRow, RemovedRuleRow, RuleIndexRow, RuleRow

from ..rule_arguments import (
    AliasSelector,
    AllSelector,
    CodeSelector,
    EmptySelectorError,
    EngineSelectorError,
    MalformedSelectorError,
    RemovedRuleSelectorError,
    RuleNameSelectorError,
    SelectorValue,
    UnknownSelectorError,
)


class SampleIndex:
    """A small rule index: two groups, and a rule with an alias code and a removed rule."""

    RULES: Final[tuple[RuleIndexRow, ...]] = (
        ConditionRow('LC001', 'invalid-utf8', 'error'),
        RuleRow('LC304', 'empty-section', 'deny', ('MD040',)),
        RuleRow('LC306', 'missing-section', 'deny', ()),
        RemovedRuleRow('OUT010', 'retired-rule'),
    )

    def find(self, key: str, /) -> RuleIndexRow | None:
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
@pytest.mark.unit
class TestSelectorValueParse:
    def test_parse_with_each_form_parses_the_form(self) -> None:
        #: Given
        raw = 'ALL,LC304,MD040'

        #: When
        parsed = SelectorValue.parse(raw, SAMPLE_INDEX)

        #: Then
        assert parsed == SelectorValue(
            (
                AllSelector(),
                CodeSelector('LC304'),
                AliasSelector('MD040', CodeSelector('LC304')),
            )
        ), 'ALL, a full code and an alias code each parse to their form'

    def test_parse_with_whitespace_around_selectors_strips_it(self) -> None:
        #: Given
        raw = ' LC304 , LC306'

        #: When
        parsed = SelectorValue.parse(raw, SAMPLE_INDEX)

        #: Then
        assert parsed == SelectorValue((CodeSelector('LC304'), CodeSelector('LC306'))), (
            'each selector of a value is stripped, in the order typed'
        )

    def test_parse_with_a_trailing_comma_raises_empty_selector_error(self) -> None:
        #: Given
        raw = 'LC304,'

        #: When
        with pytest.raises(EmptySelectorError) as exc_info:
            SelectorValue.parse(raw, SAMPLE_INDEX)

        #: Then
        assert exc_info.value.value == 'LC304,', 'the error names the value as typed'

    def test_parse_with_an_empty_value_raises_empty_selector_error(self) -> None:
        #: Given
        raw = ''

        #: When
        with pytest.raises(EmptySelectorError) as exc_info:
            SelectorValue.parse(raw, SAMPLE_INDEX)

        #: Then
        assert exc_info.value.value == '', 'an empty value holds one empty selector, named as typed'

    def test_parse_with_a_lowercase_group_raises_malformed_selector_error(self) -> None:
        #: Given
        raw = 'LC306,out'

        #: When
        with pytest.raises(MalformedSelectorError) as exc_info:
            SelectorValue.parse(raw, SAMPLE_INDEX)

        #: Then
        assert exc_info.value.text == 'out', 'lowercase selector syntax is malformed'

    def test_parse_with_a_hyphen_after_the_group_raises_malformed_selector_error(self) -> None:
        #: Given
        raw = 'OUT-1'

        #: When
        with pytest.raises(MalformedSelectorError) as exc_info:
            SelectorValue.parse(raw, SAMPLE_INDEX)

        #: Then
        assert exc_info.value.text == 'OUT-1', 'hyphens do not form a selector'

    def test_parse_with_four_digits_raises_malformed_selector_error(self) -> None:
        #: Given
        raw = 'OUT1234'

        #: When
        with pytest.raises(UnknownSelectorError) as exc_info:
            SelectorValue.parse(raw, SAMPLE_INDEX)

        #: Then
        assert exc_info.value.text == 'OUT1234', 'more digits than a code holds is no code nor prefix'

    def test_parse_with_a_zero_code_raises_malformed_selector_error(self) -> None:
        #: Given
        raw = 'OUT000'

        #: When
        with pytest.raises(UnknownSelectorError) as exc_info:
            SelectorValue.parse(raw, SAMPLE_INDEX)

        #: Then
        assert exc_info.value.text == 'OUT000', 'a full code with no indexed rule is unknown'

    def test_parse_with_digits_after_all_raises_malformed_selector_error(self) -> None:
        #: Given
        raw = 'ALL1'

        #: When
        with pytest.raises(UnknownSelectorError) as exc_info:
            SelectorValue.parse(raw, SAMPLE_INDEX)

        #: Then
        assert exc_info.value.text == 'ALL1', 'a well-shaped but unknown selector is unknown'

    def test_parse_with_an_underscored_name_raises_malformed_selector_error(self) -> None:
        #: Given
        raw = 'Empty_Section'

        #: When
        with pytest.raises(MalformedSelectorError) as exc_info:
            SelectorValue.parse(raw, SAMPLE_INDEX)

        #: Then
        assert exc_info.value.text == 'Empty_Section', 'underscores do not form a selector'

    def test_parse_with_only_digits_raises_malformed_selector_error(self) -> None:
        #: Given
        raw = '123'

        #: When
        with pytest.raises(UnknownSelectorError) as exc_info:
            SelectorValue.parse(raw, SAMPLE_INDEX)

        #: Then
        assert exc_info.value.text == '123', 'a well-shaped but unknown selector is unknown'

    def test_parse_with_whitespace_inside_a_code_raises_malformed_selector_error(self) -> None:
        #: Given
        raw = 'OUT 004'

        #: When
        with pytest.raises(MalformedSelectorError) as exc_info:
            SelectorValue.parse(raw, SAMPLE_INDEX)

        #: Then
        assert exc_info.value.text == 'OUT 004', 'only the whitespace around a selector is stripped'

    def test_parse_with_a_lowercase_all_raises_malformed_selector_error(self) -> None:
        #: Given
        raw = 'all'

        #: When
        with pytest.raises(MalformedSelectorError) as exc_info:
            SelectorValue.parse(raw, SAMPLE_INDEX)

        #: Then
        assert exc_info.value.text == 'all', 'ALL is matched as spelled'

    def test_parse_with_a_letter_after_the_group_raises_malformed_selector_error(self) -> None:
        #: Given
        raw = 'OUTx'

        #: When
        with pytest.raises(MalformedSelectorError) as exc_info:
            SelectorValue.parse(raw, SAMPLE_INDEX)

        #: Then
        assert exc_info.value.text == 'OUTx', 'a group prefix is uppercase letters only'

    def test_parse_with_a_doubled_hyphen_name_raises_malformed_selector_error(self) -> None:
        #: Given
        raw = 'empty--section'

        #: When
        with pytest.raises(MalformedSelectorError) as exc_info:
            SelectorValue.parse(raw, SAMPLE_INDEX)

        #: Then
        assert exc_info.value.text == 'empty--section', 'a text of no form is malformed, whatever it resembles'

    def test_parse_with_a_code_of_a_group_no_rule_has_raises_unknown_selector_error(self) -> None:
        #: Given
        raw = 'ZZZ004'

        #: When
        with pytest.raises(UnknownSelectorError) as exc_info:
            SelectorValue.parse(raw, SAMPLE_INDEX)

        #: Then
        assert exc_info.value.text == 'ZZZ004', 'a well-formed code in no group is unknown'

    def test_parse_with_a_code_prefix_of_a_group_no_rule_has_raises_unknown_selector_error(self) -> None:
        #: Given
        raw = 'ZZZ0'

        #: When
        with pytest.raises(UnknownSelectorError) as exc_info:
            SelectorValue.parse(raw, SAMPLE_INDEX)

        #: Then
        assert exc_info.value.text == 'ZZZ0', 'a well-formed code prefix of no group is unknown'

    def test_parse_with_a_code_of_a_group_that_no_rule_numbers_raises_unknown_selector_error(self) -> None:
        #: Given
        raw = 'LC307'

        #: When
        with pytest.raises(UnknownSelectorError) as exc_info:
            SelectorValue.parse(raw, SAMPLE_INDEX)

        #: Then
        assert exc_info.value.text == 'LC307', 'a well-formed code of a group that has no such number is unknown'

    def test_parse_with_a_code_no_rule_has_raises_unknown_selector_error(self) -> None:
        #: Given
        raw = 'OUT999'

        #: When
        with pytest.raises(UnknownSelectorError) as exc_info:
            SelectorValue.parse(raw, SAMPLE_INDEX)

        #: Then
        assert exc_info.value.text == 'OUT999', 'a well-formed code no rule has is unknown'

    def test_parse_with_a_group_no_rule_has_raises_unknown_selector_error(self) -> None:
        #: Given
        raw = 'ZZZ'

        #: When
        with pytest.raises(UnknownSelectorError) as exc_info:
            SelectorValue.parse(raw, SAMPLE_INDEX)

        #: Then
        assert exc_info.value.text == 'ZZZ', 'a well-formed prefix no group has is unknown'

    def test_parse_with_a_code_prefix_no_rule_starts_raises_unknown_selector_error(self) -> None:
        #: Given
        raw = 'OUT9'

        #: When
        with pytest.raises(UnknownSelectorError) as exc_info:
            SelectorValue.parse(raw, SAMPLE_INDEX)

        #: Then
        assert exc_info.value.text == 'OUT9', 'a code prefix no rule starts is unknown'

    def test_parse_with_a_code_prefix_only_a_removed_rule_starts_raises_unknown_selector_error(self) -> None:
        #: Given
        raw = 'OUT01'

        #: When
        with pytest.raises(UnknownSelectorError) as exc_info:
            SelectorValue.parse(raw, SAMPLE_INDEX)

        #: Then
        assert exc_info.value.text == 'OUT01', 'a code prefix only a removed rule starts is unknown'

    def test_parse_with_an_alias_code_no_rule_declares_raises_unknown_selector_error(self) -> None:
        #: Given
        raw = 'MD999'

        #: When
        with pytest.raises(UnknownSelectorError) as exc_info:
            SelectorValue.parse(raw, SAMPLE_INDEX)

        #: Then
        assert exc_info.value.text == 'MD999', 'an alias code is one exactly when a rule declares it'

    def test_parse_with_a_rule_name_raises_rule_name_selector_error(self) -> None:
        #: Given
        raw = 'empty-section'

        #: When
        with pytest.raises(RuleNameSelectorError) as exc_info:
            SelectorValue.parse(raw, SAMPLE_INDEX)

        #: Then
        assert exc_info.value.code == 'LC304', 'the error carries the code to write instead'
        assert 'LC304' in str(exc_info.value), 'the message names the code to write instead'

    def test_parse_with_the_engine_prefix_raises_unknown_selector_error(self) -> None:
        #: Given
        raw = 'LC'

        #: When
        with pytest.raises(UnknownSelectorError) as exc_info:
            SelectorValue.parse(raw, SAMPLE_INDEX)

        #: Then
        assert exc_info.value.text == 'LC', 'the shared code prefix is not a selector'

    def test_parse_with_an_engine_code_prefix_raises_unknown_selector_error(self) -> None:
        #: Given
        raw = 'LC9'

        #: When
        with pytest.raises(UnknownSelectorError) as exc_info:
            SelectorValue.parse(raw, SAMPLE_INDEX)

        #: Then
        assert exc_info.value.text == 'LC9', 'a partial code is not a selector'

    def test_parse_with_an_engine_code_raises_engine_selector_error(self) -> None:
        #: Given
        raw = 'LC001'

        #: When
        with pytest.raises(EngineSelectorError) as exc_info:
            SelectorValue.parse(raw, SAMPLE_INDEX)

        #: Then
        assert exc_info.value.text == 'LC001', "an engine condition's code cannot be selected"

    def test_parse_with_an_engine_name_raises_engine_selector_error(self) -> None:
        #: Given
        raw = 'invalid-utf8'

        #: When
        with pytest.raises(EngineSelectorError) as exc_info:
            SelectorValue.parse(raw, SAMPLE_INDEX)

        #: Then
        assert exc_info.value.text == 'invalid-utf8', "an engine condition's name cannot be selected"

    def test_parse_with_a_removed_code_raises_removed_rule_selector_error(self) -> None:
        #: Given
        raw = 'OUT010'

        #: When
        with pytest.raises(RemovedRuleSelectorError) as exc_info:
            SelectorValue.parse(raw, SAMPLE_INDEX)

        #: Then
        assert exc_info.value.code == 'OUT010', 'the error carries the removed rule code'
        assert 'lorecraft rule OUT010' in str(exc_info.value), 'the message names the command that says more'

    def test_parse_with_a_removed_name_raises_removed_rule_selector_error(self) -> None:
        #: Given
        raw = 'retired-rule'

        #: When
        with pytest.raises(RemovedRuleSelectorError) as exc_info:
            SelectorValue.parse(raw, SAMPLE_INDEX)

        #: Then
        assert exc_info.value.code == 'OUT010', 'a removed rule is refused by its name too, naming its code'


@pytest.mark.unit
class TestSelectorValueStr:
    def test_str_with_each_form_returns_the_values_joined_by_commas(self) -> None:
        #: Given
        value = SelectorValue(
            (
                AllSelector(),
                CodeSelector('LC304'),
                AliasSelector('MD040', CodeSelector('LC304')),
            )
        )

        #: When
        text = str(value)

        #: Then
        assert text == 'ALL,LC304,MD040', 'each selector prints as typed, a code zero-padded'
