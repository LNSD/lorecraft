"""A rule's declaration: its identity values."""

import pytest

from ..rule import (
    AliasCode,
    EmptyAliasLinterError,
    EmptyRuleGroupTitleError,
    InvalidAliasCodeError,
    InvalidRuleGroupPrefixError,
    LeadingZeroReleaseError,
    Level,
    MalformedReleaseError,
    Release,
    RuleCode,
    RuleGroup,
    RuleNumberOutOfRangeError,
)
from .sample_rules.groups import SAMPLE


@pytest.mark.unit
class TestRelease:
    def test_parse_with_three_components_returns_the_release(self) -> None:
        #: Given
        raw = '0.3.0'

        #: When
        release = Release.parse(raw)

        #: Then
        assert str(release) == raw, 'a release is kept exactly as spelled'

    def test_parse_with_a_multi_digit_component_returns_the_release(self) -> None:
        #: Given
        raw = '1.10.200'

        #: When
        release = Release.parse(raw)

        #: Then
        assert str(release) == raw, 'a component may have several digits'

    def test_parse_with_a_v_prefix_raises_malformed_release_error(self) -> None:
        #: Given
        raw = 'v0.3.0'

        #: When
        with pytest.raises(MalformedReleaseError) as exc_info:
            Release.parse(raw)

        #: Then
        assert exc_info.value.value == raw, 'the error keeps the release with a prefix'

    def test_parse_with_two_components_raises_malformed_release_error(self) -> None:
        #: Given
        raw = '0.3'

        #: When
        with pytest.raises(MalformedReleaseError) as exc_info:
            Release.parse(raw)

        #: Then
        assert exc_info.value.value == raw, 'the error keeps the release missing its patch'

    def test_parse_with_four_components_raises_malformed_release_error(self) -> None:
        #: Given
        raw = '0.3.0.1'

        #: When
        with pytest.raises(MalformedReleaseError) as exc_info:
            Release.parse(raw)

        #: Then
        assert exc_info.value.value == raw, 'the error keeps the release with a fourth component'

    def test_parse_with_a_pre_release_suffix_raises_malformed_release_error(self) -> None:
        #: Given
        raw = '0.3.0-rc1'

        #: When
        with pytest.raises(MalformedReleaseError) as exc_info:
            Release.parse(raw)

        #: Then
        assert exc_info.value.value == raw, 'the error keeps the release with a suffix'

    def test_parse_with_an_empty_component_raises_malformed_release_error(self) -> None:
        #: Given
        raw = '0..3'

        #: When
        with pytest.raises(MalformedReleaseError) as exc_info:
            Release.parse(raw)

        #: Then
        assert exc_info.value.value == raw, 'the error keeps the release with an empty component'

    def test_parse_with_a_non_ascii_digit_raises_malformed_release_error(self) -> None:
        #: Given
        raw = '0.\N{ARABIC-INDIC DIGIT THREE}.0'

        #: When
        with pytest.raises(MalformedReleaseError) as exc_info:
            Release.parse(raw)

        #: Then
        assert exc_info.value.value == raw, 'the error keeps the release with a digit outside ASCII'

    def test_parse_with_a_leading_zero_raises_leading_zero_release_error(self) -> None:
        #: Given
        raw = '0.03.0'

        #: When
        with pytest.raises(LeadingZeroReleaseError) as exc_info:
            Release.parse(raw)

        #: Then
        assert exc_info.value.value == raw, 'the error keeps the release'
        assert exc_info.value.component == '03', 'the error names the component with the leading zero'


@pytest.mark.unit
class TestRuleGroup:
    def test_rule_group_with_an_empty_prefix_raises_invalid_rule_group_prefix_error(self) -> None:
        #: Given
        prefix = ''

        #: When
        with pytest.raises(InvalidRuleGroupPrefixError) as exc_info:
            RuleGroup(prefix, 'Outline')

        #: Then
        assert exc_info.value.prefix == prefix, 'the error keeps the empty prefix'

    def test_rule_group_with_a_lowercase_prefix_raises_invalid_rule_group_prefix_error(self) -> None:
        #: Given
        prefix = 'Out'

        #: When
        with pytest.raises(InvalidRuleGroupPrefixError) as exc_info:
            RuleGroup(prefix, 'Outline')

        #: Then
        assert exc_info.value.prefix == prefix, 'the error keeps the prefix with a lowercase letter'

    def test_rule_group_with_a_digit_in_the_prefix_raises_invalid_rule_group_prefix_error(self) -> None:
        #: Given
        prefix = 'OUT2'

        #: When
        with pytest.raises(InvalidRuleGroupPrefixError) as exc_info:
            RuleGroup(prefix, 'Outline')

        #: Then
        assert exc_info.value.prefix == prefix, 'the error keeps the prefix with a digit'

    def test_rule_group_with_an_empty_title_raises_empty_rule_group_title_error(self) -> None:
        #: Given
        title = ''

        #: When
        with pytest.raises(EmptyRuleGroupTitleError) as exc_info:
            RuleGroup('OUT', title)

        #: Then
        assert exc_info.value.prefix == 'OUT', 'the error names the group with no title'


@pytest.mark.unit
class TestRuleCode:
    def test_str_with_a_one_digit_number_pads_it_to_three_digits(self) -> None:
        #: Given
        code = RuleCode(RuleGroup('OUT', 'Outline'), 2)

        #: When
        printed = str(code)

        #: Then
        assert printed == 'OUT002', "a code prints as its group's prefix and three digits"

    def test_str_with_the_largest_number_prints_it_unpadded(self) -> None:
        #: Given
        code = RuleCode(RuleGroup('OUT', 'Outline'), 999)

        #: When
        printed = str(code)

        #: Then
        assert printed == 'OUT999', 'a three-digit number needs no padding'

    def test_rule_code_with_number_zero_raises_rule_number_out_of_range_error(self) -> None:
        #: Given
        number = 0

        #: When
        with pytest.raises(RuleNumberOutOfRangeError) as exc_info:
            RuleCode(SAMPLE, number)

        #: Then
        assert exc_info.value.group is SAMPLE, 'the error names the group of the code'
        assert exc_info.value.number == number, 'the error keeps the number below the range'

    def test_rule_code_with_a_four_digit_number_raises_rule_number_out_of_range_error(self) -> None:
        #: Given
        number = 1000

        #: When
        with pytest.raises(RuleNumberOutOfRangeError) as exc_info:
            RuleCode(SAMPLE, number)

        #: Then
        assert exc_info.value.number == number, 'the error keeps the number that would print four digits'


@pytest.mark.unit
class TestAliasCode:
    def test_str_with_a_linter_and_a_code_prints_the_code_alone(self) -> None:
        #: Given
        alias = AliasCode('markdownlint', 'MD040')

        #: When
        printed = str(alias)

        #: Then
        assert printed == 'MD040', 'an alias code prints as the upstream code a user types'

    def test_alias_code_with_an_empty_linter_raises_empty_alias_linter_error(self) -> None:
        #: Given
        linter = ''

        #: When
        with pytest.raises(EmptyAliasLinterError) as exc_info:
            AliasCode(linter, 'MD040')

        #: Then
        assert exc_info.value.code == 'MD040', 'the error names the code with no linter'

    def test_alias_code_with_an_empty_code_raises_invalid_alias_code_error(self) -> None:
        #: Given
        code = ''

        #: When
        with pytest.raises(InvalidAliasCodeError) as exc_info:
            AliasCode('markdownlint', code)

        #: Then
        assert exc_info.value.linter == 'markdownlint', 'the error names the linter'
        assert exc_info.value.code == code, 'the error keeps the empty code'

    def test_alias_code_with_whitespace_in_the_code_raises_invalid_alias_code_error(self) -> None:
        #: Given
        code = 'MD 040'

        #: When
        with pytest.raises(InvalidAliasCodeError) as exc_info:
            AliasCode('markdownlint', code)

        #: Then
        assert exc_info.value.code == code, 'the error keeps the code holding a space'


@pytest.mark.unit
class TestLevel:
    def test_level_values_in_declaration_order_spell_allow_warn_deny(self) -> None:
        #: Given
        expected = ('allow', 'warn', 'deny')

        #: When
        spelled = tuple(level.value for level in Level)

        #: Then
        assert spelled == expected, 'the three levels, in order, are spelled allow, warn and deny'
