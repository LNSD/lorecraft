"""The one-run selection: a rule is kept when its most specific select match is more specific than any ignore match."""

from typing import Final

import pytest

from lorecraft.rules.declaration import RuleCode
from lorecraft.rules.tests.sample_rules.groups import LAYOUT, SAMPLE

from ..selection import AllRules, InvalidRuleCodePrefixError, RuleCodePrefix, RuleSelection

SMP001: Final[RuleCode] = RuleCode(SAMPLE, 1)
SMP002: Final[RuleCode] = RuleCode(SAMPLE, 2)
SMP010: Final[RuleCode] = RuleCode(SAMPLE, 10)
SMP100: Final[RuleCode] = RuleCode(SAMPLE, 100)
LAYS001: Final[RuleCode] = RuleCode(LAYOUT, 1)

SMP0: Final[RuleCodePrefix] = RuleCodePrefix(SAMPLE, '0')
SMP00: Final[RuleCodePrefix] = RuleCodePrefix(SAMPLE, '00')

EVERY_RULE: Final[RuleSelection] = RuleSelection(select=frozenset({AllRules()}), ignore=frozenset())
"""The selection of a run given neither `--select` nor `--ignore`: every rule is kept."""


@pytest.mark.unit
class TestRuleCodePrefix:
    def test_rule_code_prefix_with_one_digit_is_prefix_of_the_codes_whose_number_starts_with_it(self) -> None:
        #: Given
        prefix = SMP0

        #: When
        is_prefix = (
            prefix.is_prefix_of(SMP001),
            prefix.is_prefix_of(SMP010),
            prefix.is_prefix_of(SMP100),
            prefix.is_prefix_of(LAYS001),
        )

        #: Then
        assert is_prefix == (True, True, False, False), (
            "a prefix starts its group's codes whose zero-padded number does"
        )

    def test_rule_code_prefix_with_two_digits_is_prefix_of_fewer_codes(self) -> None:
        #: Given
        prefix = SMP00

        #: When
        is_prefix = (prefix.is_prefix_of(SMP001), prefix.is_prefix_of(SMP010))

        #: Then
        assert is_prefix == (True, False), 'a second digit narrows the codes a prefix starts'

    def test_rule_code_prefix_with_two_digits_prints_as_the_group_prefix_then_the_digits(self) -> None:
        #: Given
        prefix = SMP00

        #: When
        printed = str(prefix)

        #: Then
        assert printed == 'SMP00', 'a prefix prints as typed'

    def test_parse_with_three_digits_raises_invalid_rule_code_prefix_error(self) -> None:
        #: Given
        digits = '000'

        #: When
        with pytest.raises(InvalidRuleCodePrefixError) as exc_info:
            RuleCodePrefix.parse(SAMPLE, digits)

        #: Then
        assert exc_info.value.digits == '000', 'three digits are a whole code, not a prefix'

    def test_parse_with_no_digit_raises_invalid_rule_code_prefix_error(self) -> None:
        #: Given
        digits = ''

        #: When
        with pytest.raises(InvalidRuleCodePrefixError) as exc_info:
            RuleCodePrefix.parse(SAMPLE, digits)

        #: Then
        assert exc_info.value.digits == '', 'no digit is the group, not a prefix of its codes'

    def test_parse_with_a_letter_raises_invalid_rule_code_prefix_error(self) -> None:
        #: Given
        digits = '0x'

        #: When
        with pytest.raises(InvalidRuleCodePrefixError) as exc_info:
            RuleCodePrefix.parse(SAMPLE, digits)

        #: Then
        assert exc_info.value.digits == '0x', 'a prefix holds digits only'


@pytest.mark.unit
class TestRuleSelectionIsKept:
    def test_is_kept_with_every_rule_keeps_any_code(self) -> None:
        #: Given
        selection = EVERY_RULE

        #: When
        kept = selection.is_kept(LAYS001)

        #: Then
        assert kept, 'no --select keeps every rule'

    def test_is_kept_with_a_selected_code_keeps_that_rule_alone(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({SMP001}), ignore=frozenset())

        #: When
        kept = (selection.is_kept(SMP001), selection.is_kept(SMP002))

        #: Then
        assert kept == (True, False), 'a code selects its rule, and no other rule of its group'

    def test_is_kept_with_a_selected_group_keeps_each_of_its_rules_and_no_other(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({SAMPLE}), ignore=frozenset())

        #: When
        kept = (selection.is_kept(SMP001), selection.is_kept(SMP002), selection.is_kept(LAYS001))

        #: Then
        assert kept == (True, True, False), "a prefix selects every rule of its group, and no other group's"

    def test_is_kept_with_a_selected_code_prefix_keeps_the_rules_it_starts(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({SMP0}), ignore=frozenset())

        #: When
        kept = (selection.is_kept(SMP001), selection.is_kept(SMP010), selection.is_kept(SMP100))

        #: Then
        assert kept == (True, True, False), 'a code prefix selects the rules whose code it starts'

    def test_is_kept_with_an_ignored_code_and_every_rule_selected_leaves_that_rule_out(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({AllRules()}), ignore=frozenset({SMP001}))

        #: When
        kept = (selection.is_kept(SMP001), selection.is_kept(SMP002))

        #: Then
        assert kept == (False, True), 'an ignored code leaves its rule out, and only it'


@pytest.mark.unit
class TestRuleSelectionIsKeptBySpecificity:
    def test_is_kept_with_all_selected_and_a_group_ignored_leaves_the_group_out(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({AllRules()}), ignore=frozenset({SAMPLE}))

        #: When
        kept = (selection.is_kept(SMP001), selection.is_kept(LAYS001))

        #: Then
        assert kept == (False, True), 'a group ignored is more specific than ALL selected'

    def test_is_kept_with_a_group_selected_and_all_ignored_keeps_the_group(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({SAMPLE}), ignore=frozenset({AllRules()}))

        #: When
        kept = (selection.is_kept(SMP001), selection.is_kept(LAYS001))

        #: Then
        assert kept == (True, False), 'a group selected is more specific than ALL ignored'

    def test_is_kept_with_all_selected_and_a_code_prefix_ignored_leaves_its_rules_out(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({AllRules()}), ignore=frozenset({SMP0}))

        #: When
        kept = (selection.is_kept(SMP001), selection.is_kept(SMP100))

        #: Then
        assert kept == (False, True), 'a code prefix ignored is more specific than ALL selected'

    def test_is_kept_with_a_code_prefix_selected_and_all_ignored_keeps_its_rules(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({SMP0}), ignore=frozenset({AllRules()}))

        #: When
        kept = (selection.is_kept(SMP001), selection.is_kept(SMP100))

        #: Then
        assert kept == (True, False), 'a code prefix selected is more specific than ALL ignored'

    def test_is_kept_with_all_selected_and_a_code_ignored_leaves_that_rule_out(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({AllRules()}), ignore=frozenset({SMP001}))

        #: When
        kept = (selection.is_kept(SMP001), selection.is_kept(SMP002))

        #: Then
        assert kept == (False, True), 'a code ignored is more specific than ALL selected'

    def test_is_kept_with_a_code_selected_and_all_ignored_keeps_that_rule_alone(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({SMP001}), ignore=frozenset({AllRules()}))

        #: When
        kept = (selection.is_kept(SMP001), selection.is_kept(SMP002))

        #: Then
        assert kept == (True, False), 'a code selected is more specific than ALL ignored'

    def test_is_kept_with_a_group_selected_and_a_code_prefix_ignored_leaves_its_rules_out(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({SAMPLE}), ignore=frozenset({SMP0}))

        #: When
        kept = (selection.is_kept(SMP001), selection.is_kept(SMP100))

        #: Then
        assert kept == (False, True), 'a code prefix ignored is more specific than its group selected'

    def test_is_kept_with_a_code_prefix_selected_and_its_group_ignored_keeps_its_rules(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({SMP0}), ignore=frozenset({SAMPLE}))

        #: When
        kept = (selection.is_kept(SMP001), selection.is_kept(SMP100))

        #: Then
        assert kept == (True, False), 'a code prefix selected is more specific than its group ignored'

    def test_is_kept_with_a_group_selected_and_one_of_its_codes_ignored_leaves_that_rule_out(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({SAMPLE}), ignore=frozenset({SMP002}))

        #: When
        kept = (selection.is_kept(SMP001), selection.is_kept(SMP002))

        #: Then
        assert kept == (True, False), 'a code ignored is more specific than its group selected'

    def test_is_kept_with_a_code_selected_and_its_group_ignored_keeps_that_rule_alone(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({SMP001}), ignore=frozenset({SAMPLE}))

        #: When
        kept = (selection.is_kept(SMP001), selection.is_kept(SMP002))

        #: Then
        assert kept == (True, False), 'a code selected is more specific than its group ignored'

    def test_is_kept_with_one_digit_selected_and_two_digits_ignored_leaves_the_longer_prefixs_rules_out(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({SMP0}), ignore=frozenset({SMP00}))

        #: When
        kept = (selection.is_kept(SMP001), selection.is_kept(SMP010))

        #: Then
        assert kept == (False, True), 'a prefix with more digits is the more specific'

    def test_is_kept_with_two_digits_selected_and_one_digit_ignored_keeps_the_longer_prefixs_rules(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({SMP00}), ignore=frozenset({SMP0}))

        #: When
        kept = (selection.is_kept(SMP001), selection.is_kept(SMP010))

        #: Then
        assert kept == (True, False), 'a prefix with more digits is the more specific'

    def test_is_kept_with_a_code_prefix_selected_and_a_code_ignored_leaves_that_rule_out(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({SMP00}), ignore=frozenset({SMP001}))

        #: When
        kept = (selection.is_kept(SMP001), selection.is_kept(SMP002))

        #: Then
        assert kept == (False, True), 'a code ignored is more specific than a prefix of it selected'

    def test_is_kept_with_a_code_selected_and_a_code_prefix_ignored_keeps_that_rule_alone(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({SMP001}), ignore=frozenset({SMP00}))

        #: When
        kept = (selection.is_kept(SMP001), selection.is_kept(SMP002))

        #: Then
        assert kept == (True, False), 'a code selected is more specific than a prefix of it ignored'

    def test_is_kept_with_all_selected_and_ignored_keeps_nothing(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({AllRules()}), ignore=frozenset({AllRules()}))

        #: When
        kept = selection.is_kept(SMP001)

        #: Then
        assert not kept, 'ignoring wins a tie'

    def test_is_kept_with_a_group_selected_and_ignored_keeps_none_of_its_rules(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({SAMPLE, LAYOUT}), ignore=frozenset({SAMPLE}))

        #: When
        kept = (selection.is_kept(SMP001), selection.is_kept(LAYS001))

        #: Then
        assert kept == (False, True), 'ignoring wins a tie, and leaves the other group selected'

    def test_is_kept_with_a_code_prefix_selected_and_ignored_keeps_none_of_its_rules(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({SMP0}), ignore=frozenset({SMP0}))

        #: When
        kept = selection.is_kept(SMP001)

        #: Then
        assert not kept, 'ignoring wins a tie'

    def test_is_kept_with_a_code_selected_and_ignored_leaves_that_rule_out(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({SMP001}), ignore=frozenset({SMP001}))

        #: When
        kept = selection.is_kept(SMP001)

        #: Then
        assert not kept, 'ignoring wins a tie'

    def test_is_kept_with_a_code_and_its_group_selected_and_the_code_ignored_leaves_that_rule_out(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({SAMPLE, SMP001}), ignore=frozenset({SMP001}))

        #: When
        kept = (selection.is_kept(SMP001), selection.is_kept(SMP002))

        #: Then
        assert kept == (False, True), 'the most specific match of each option decides, and ignoring wins the tie'
