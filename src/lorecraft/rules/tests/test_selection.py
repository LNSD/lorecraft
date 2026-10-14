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
    def test_is_prefix_of_with_a_code_whose_number_starts_with_the_digit_returns_true(self) -> None:
        #: Given
        prefix = SMP0
        code = SMP001

        #: When
        is_prefix = prefix.is_prefix_of(code)

        #: Then
        assert is_prefix, 'a prefix starts the codes of its group whose zero-padded number starts with it'

    def test_is_prefix_of_with_a_code_whose_number_starts_with_the_digit_and_has_another_second_digit_returns_true(
        self,
    ) -> None:
        #: Given
        prefix = SMP0
        code = SMP010

        #: When
        is_prefix = prefix.is_prefix_of(code)

        #: Then
        assert is_prefix, 'a prefix starts the codes of its group whose zero-padded number starts with it'

    def test_is_prefix_of_with_a_code_whose_number_does_not_start_with_the_digit_returns_false(self) -> None:
        #: Given
        prefix = SMP0
        code = SMP100

        #: When
        is_prefix = prefix.is_prefix_of(code)

        #: Then
        assert not is_prefix, 'a prefix does not start a code whose zero-padded number starts with another digit'

    def test_is_prefix_of_with_a_code_of_another_group_returns_false(self) -> None:
        #: Given
        prefix = SMP0
        code = LAYS001

        #: When
        is_prefix = prefix.is_prefix_of(code)

        #: Then
        assert not is_prefix, 'a prefix starts the codes of its own group alone'

    def test_is_prefix_of_with_two_digits_and_a_code_starting_with_both_returns_true(self) -> None:
        #: Given
        prefix = SMP00
        code = SMP001

        #: When
        is_prefix = prefix.is_prefix_of(code)

        #: Then
        assert is_prefix, 'a second digit narrows the codes a prefix starts, and this one still starts it'

    def test_is_prefix_of_with_two_digits_and_a_code_starting_with_the_first_only_returns_false(self) -> None:
        #: Given
        prefix = SMP00
        code = SMP010

        #: When
        is_prefix = prefix.is_prefix_of(code)

        #: Then
        assert not is_prefix, 'a second digit narrows the codes a prefix starts, and this one no longer does'

    def test_rule_code_prefix_with_two_digits_prints_as_the_group_prefix_then_the_digits(self) -> None:
        #: Given
        prefix = SMP00

        #: When
        printed = str(prefix)

        #: Then
        assert printed == 'SMP00', 'a prefix prints as typed'

    def test_init_with_three_digits_raises_invalid_rule_code_prefix_error(self) -> None:
        #: Given
        digits = '000'

        #: When
        with pytest.raises(InvalidRuleCodePrefixError) as exc_info:
            RuleCodePrefix(SAMPLE, digits)

        #: Then
        assert exc_info.value.digits == '000', 'three digits are a whole code, not a prefix'

    def test_init_with_no_digit_raises_invalid_rule_code_prefix_error(self) -> None:
        #: Given
        digits = ''

        #: When
        with pytest.raises(InvalidRuleCodePrefixError) as exc_info:
            RuleCodePrefix(SAMPLE, digits)

        #: Then
        assert exc_info.value.digits == '', 'no digit is the group, not a prefix of its codes'

    def test_init_with_a_letter_raises_invalid_rule_code_prefix_error(self) -> None:
        #: Given
        digits = '0x'

        #: When
        with pytest.raises(InvalidRuleCodePrefixError) as exc_info:
            RuleCodePrefix(SAMPLE, digits)

        #: Then
        assert exc_info.value.digits == '0x', 'a prefix holds digits only'


@pytest.mark.unit
class TestRuleSelectionIsKept:
    def test_is_kept_with_every_rule_selected_keeps_any_code(self) -> None:
        #: Given
        selection = EVERY_RULE
        code = LAYS001

        #: When
        kept = selection.is_kept(code)

        #: Then
        assert kept, 'no --select keeps every rule'

    def test_is_kept_with_a_selected_code_keeps_that_rule(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({SMP001}), ignore=frozenset())
        code = SMP001

        #: When
        kept = selection.is_kept(code)

        #: Then
        assert kept, 'a code selects its rule'

    def test_is_kept_with_a_selected_code_leaves_out_another_rule_of_its_group(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({SMP001}), ignore=frozenset())
        code = SMP002

        #: When
        kept = selection.is_kept(code)

        #: Then
        assert not kept, 'a code selects no other rule of its group'

    def test_is_kept_with_a_selected_group_keeps_a_rule_of_the_group(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({SAMPLE}), ignore=frozenset())
        code = SMP001

        #: When
        kept = selection.is_kept(code)

        #: Then
        assert kept, 'a group selects every rule it holds'

    def test_is_kept_with_a_selected_group_keeps_another_rule_of_the_group(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({SAMPLE}), ignore=frozenset())
        code = SMP002

        #: When
        kept = selection.is_kept(code)

        #: Then
        assert kept, 'a group selects every rule it holds'

    def test_is_kept_with_a_selected_group_leaves_out_a_rule_of_another_group(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({SAMPLE}), ignore=frozenset())
        code = LAYS001

        #: When
        kept = selection.is_kept(code)

        #: Then
        assert not kept, "a group selects no other group's rule"

    def test_is_kept_with_a_selected_code_prefix_keeps_a_rule_it_starts(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({SMP0}), ignore=frozenset())
        code = SMP001

        #: When
        kept = selection.is_kept(code)

        #: Then
        assert kept, 'a code prefix selects the rules whose code it starts'

    def test_is_kept_with_a_selected_code_prefix_keeps_another_rule_it_starts(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({SMP0}), ignore=frozenset())
        code = SMP010

        #: When
        kept = selection.is_kept(code)

        #: Then
        assert kept, 'a code prefix selects the rules whose code it starts'

    def test_is_kept_with_a_selected_code_prefix_leaves_out_a_rule_it_does_not_start(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({SMP0}), ignore=frozenset())
        code = SMP100

        #: When
        kept = selection.is_kept(code)

        #: Then
        assert not kept, 'a code prefix selects no rule whose code it does not start'

    def test_is_kept_with_every_rule_selected_and_a_code_ignored_leaves_that_rule_out(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({AllRules()}), ignore=frozenset({SMP001}))
        code = SMP001

        #: When
        kept = selection.is_kept(code)

        #: Then
        assert not kept, 'an ignored code leaves its rule out'

    def test_is_kept_with_every_rule_selected_and_a_code_ignored_keeps_another_rule(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({AllRules()}), ignore=frozenset({SMP001}))
        code = SMP002

        #: When
        kept = selection.is_kept(code)

        #: Then
        assert kept, 'an ignored code leaves out its rule alone'


@pytest.mark.unit
class TestRuleSelectionIsKeptBySpecificity:
    def test_is_kept_with_all_selected_and_a_group_ignored_leaves_the_group_out(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({AllRules()}), ignore=frozenset({SAMPLE}))
        code = SMP001

        #: When
        kept = selection.is_kept(code)

        #: Then
        assert not kept, 'a group ignored is more specific than ALL selected'

    def test_is_kept_with_all_selected_and_a_group_ignored_keeps_another_group(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({AllRules()}), ignore=frozenset({SAMPLE}))
        code = LAYS001

        #: When
        kept = selection.is_kept(code)

        #: Then
        assert kept, 'a group ignored leaves out its own rules alone'

    def test_is_kept_with_a_group_selected_and_all_ignored_keeps_the_group(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({SAMPLE}), ignore=frozenset({AllRules()}))
        code = SMP001

        #: When
        kept = selection.is_kept(code)

        #: Then
        assert kept, 'a group selected is more specific than ALL ignored'

    def test_is_kept_with_a_group_selected_and_all_ignored_leaves_another_group_out(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({SAMPLE}), ignore=frozenset({AllRules()}))
        code = LAYS001

        #: When
        kept = selection.is_kept(code)

        #: Then
        assert not kept, 'ALL ignored leaves out every rule the group does not hold'

    def test_is_kept_with_all_selected_and_a_code_prefix_ignored_leaves_its_rules_out(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({AllRules()}), ignore=frozenset({SMP0}))
        code = SMP001

        #: When
        kept = selection.is_kept(code)

        #: Then
        assert not kept, 'a code prefix ignored is more specific than ALL selected'

    def test_is_kept_with_all_selected_and_a_code_prefix_ignored_keeps_a_rule_it_does_not_start(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({AllRules()}), ignore=frozenset({SMP0}))
        code = SMP100

        #: When
        kept = selection.is_kept(code)

        #: Then
        assert kept, 'a code prefix ignored leaves out the rules it starts alone'

    def test_is_kept_with_a_code_prefix_selected_and_all_ignored_keeps_its_rules(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({SMP0}), ignore=frozenset({AllRules()}))
        code = SMP001

        #: When
        kept = selection.is_kept(code)

        #: Then
        assert kept, 'a code prefix selected is more specific than ALL ignored'

    def test_is_kept_with_a_code_prefix_selected_and_all_ignored_leaves_out_a_rule_it_does_not_start(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({SMP0}), ignore=frozenset({AllRules()}))
        code = SMP100

        #: When
        kept = selection.is_kept(code)

        #: Then
        assert not kept, 'ALL ignored leaves out every rule the code prefix does not start'

    def test_is_kept_with_all_selected_and_a_code_ignored_leaves_that_rule_out(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({AllRules()}), ignore=frozenset({SMP001}))
        code = SMP001

        #: When
        kept = selection.is_kept(code)

        #: Then
        assert not kept, 'a code ignored is more specific than ALL selected'

    def test_is_kept_with_all_selected_and_a_code_ignored_keeps_another_rule(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({AllRules()}), ignore=frozenset({SMP001}))
        code = SMP002

        #: When
        kept = selection.is_kept(code)

        #: Then
        assert kept, 'a code ignored leaves out its rule alone'

    def test_is_kept_with_a_code_selected_and_all_ignored_keeps_that_rule(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({SMP001}), ignore=frozenset({AllRules()}))
        code = SMP001

        #: When
        kept = selection.is_kept(code)

        #: Then
        assert kept, 'a code selected is more specific than ALL ignored'

    def test_is_kept_with_a_code_selected_and_all_ignored_leaves_another_rule_out(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({SMP001}), ignore=frozenset({AllRules()}))
        code = SMP002

        #: When
        kept = selection.is_kept(code)

        #: Then
        assert not kept, 'ALL ignored leaves out every rule the code does not select'

    def test_is_kept_with_a_group_selected_and_a_code_prefix_ignored_leaves_its_rules_out(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({SAMPLE}), ignore=frozenset({SMP0}))
        code = SMP001

        #: When
        kept = selection.is_kept(code)

        #: Then
        assert not kept, 'a code prefix ignored is more specific than its group selected'

    def test_is_kept_with_a_group_selected_and_a_code_prefix_ignored_keeps_a_rule_it_does_not_start(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({SAMPLE}), ignore=frozenset({SMP0}))
        code = SMP100

        #: When
        kept = selection.is_kept(code)

        #: Then
        assert kept, 'a code prefix ignored leaves out the rules it starts alone'

    def test_is_kept_with_a_code_prefix_selected_and_its_group_ignored_keeps_its_rules(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({SMP0}), ignore=frozenset({SAMPLE}))
        code = SMP001

        #: When
        kept = selection.is_kept(code)

        #: Then
        assert kept, 'a code prefix selected is more specific than its group ignored'

    def test_is_kept_with_a_code_prefix_selected_and_its_group_ignored_leaves_out_a_rule_it_does_not_start(
        self,
    ) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({SMP0}), ignore=frozenset({SAMPLE}))
        code = SMP100

        #: When
        kept = selection.is_kept(code)

        #: Then
        assert not kept, 'the group ignored leaves out the rules the code prefix does not start'

    def test_is_kept_with_a_group_selected_and_one_of_its_codes_ignored_keeps_another_rule(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({SAMPLE}), ignore=frozenset({SMP002}))
        code = SMP001

        #: When
        kept = selection.is_kept(code)

        #: Then
        assert kept, 'a code ignored leaves out its rule alone'

    def test_is_kept_with_a_group_selected_and_one_of_its_codes_ignored_leaves_that_rule_out(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({SAMPLE}), ignore=frozenset({SMP002}))
        code = SMP002

        #: When
        kept = selection.is_kept(code)

        #: Then
        assert not kept, 'a code ignored is more specific than its group selected'

    def test_is_kept_with_a_code_selected_and_its_group_ignored_keeps_that_rule(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({SMP001}), ignore=frozenset({SAMPLE}))
        code = SMP001

        #: When
        kept = selection.is_kept(code)

        #: Then
        assert kept, 'a code selected is more specific than its group ignored'

    def test_is_kept_with_a_code_selected_and_its_group_ignored_leaves_another_rule_out(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({SMP001}), ignore=frozenset({SAMPLE}))
        code = SMP002

        #: When
        kept = selection.is_kept(code)

        #: Then
        assert not kept, 'the group ignored leaves out every rule the code does not select'

    def test_is_kept_with_one_digit_selected_and_two_digits_ignored_leaves_the_longer_prefixs_rules_out(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({SMP0}), ignore=frozenset({SMP00}))
        code = SMP001

        #: When
        kept = selection.is_kept(code)

        #: Then
        assert not kept, 'a prefix with more digits is the more specific'

    def test_is_kept_with_one_digit_selected_and_two_digits_ignored_keeps_a_rule_the_longer_prefix_does_not_start(
        self,
    ) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({SMP0}), ignore=frozenset({SMP00}))
        code = SMP010

        #: When
        kept = selection.is_kept(code)

        #: Then
        assert kept, 'the longer prefix ignored leaves out the rules it starts alone'

    def test_is_kept_with_two_digits_selected_and_one_digit_ignored_keeps_the_longer_prefixs_rules(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({SMP00}), ignore=frozenset({SMP0}))
        code = SMP001

        #: When
        kept = selection.is_kept(code)

        #: Then
        assert kept, 'a prefix with more digits is the more specific'

    def test_is_kept_with_two_digits_selected_and_one_digit_ignored_leaves_out_a_rule_the_longer_prefix_does_not_start(
        self,
    ) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({SMP00}), ignore=frozenset({SMP0}))
        code = SMP010

        #: When
        kept = selection.is_kept(code)

        #: Then
        assert not kept, 'the shorter prefix ignored leaves out the rules the longer one does not start'

    def test_is_kept_with_a_code_prefix_selected_and_a_code_ignored_leaves_that_rule_out(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({SMP00}), ignore=frozenset({SMP001}))
        code = SMP001

        #: When
        kept = selection.is_kept(code)

        #: Then
        assert not kept, 'a code ignored is more specific than a prefix of it selected'

    def test_is_kept_with_a_code_prefix_selected_and_a_code_ignored_keeps_another_rule_it_starts(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({SMP00}), ignore=frozenset({SMP001}))
        code = SMP002

        #: When
        kept = selection.is_kept(code)

        #: Then
        assert kept, 'a code ignored leaves out its rule alone'

    def test_is_kept_with_a_code_selected_and_a_code_prefix_ignored_keeps_that_rule(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({SMP001}), ignore=frozenset({SMP00}))
        code = SMP001

        #: When
        kept = selection.is_kept(code)

        #: Then
        assert kept, 'a code selected is more specific than a prefix of it ignored'

    def test_is_kept_with_a_code_selected_and_a_code_prefix_ignored_leaves_another_rule_out(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({SMP001}), ignore=frozenset({SMP00}))
        code = SMP002

        #: When
        kept = selection.is_kept(code)

        #: Then
        assert not kept, 'the prefix ignored leaves out every rule the code does not select'

    def test_is_kept_with_all_selected_and_ignored_keeps_nothing(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({AllRules()}), ignore=frozenset({AllRules()}))
        code = SMP001

        #: When
        kept = selection.is_kept(code)

        #: Then
        assert not kept, 'ignoring wins a tie'

    def test_is_kept_with_a_group_selected_and_ignored_leaves_its_rules_out(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({SAMPLE, LAYOUT}), ignore=frozenset({SAMPLE}))
        code = SMP001

        #: When
        kept = selection.is_kept(code)

        #: Then
        assert not kept, 'ignoring wins a tie'

    def test_is_kept_with_a_group_selected_and_ignored_keeps_the_other_selected_group(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({SAMPLE, LAYOUT}), ignore=frozenset({SAMPLE}))
        code = LAYS001

        #: When
        kept = selection.is_kept(code)

        #: Then
        assert kept, 'ignoring a group leaves the other selected group kept'

    def test_is_kept_with_a_code_prefix_selected_and_ignored_leaves_its_rules_out(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({SMP0}), ignore=frozenset({SMP0}))
        code = SMP001

        #: When
        kept = selection.is_kept(code)

        #: Then
        assert not kept, 'ignoring wins a tie'

    def test_is_kept_with_a_code_selected_and_ignored_leaves_that_rule_out(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({SMP001}), ignore=frozenset({SMP001}))
        code = SMP001

        #: When
        kept = selection.is_kept(code)

        #: Then
        assert not kept, 'ignoring wins a tie'

    def test_is_kept_with_a_code_and_its_group_selected_and_the_code_ignored_leaves_that_rule_out(self) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({SAMPLE, SMP001}), ignore=frozenset({SMP001}))
        code = SMP001

        #: When
        kept = selection.is_kept(code)

        #: Then
        assert not kept, 'the most specific match of each option decides, and ignoring wins the tie'

    def test_is_kept_with_a_code_and_its_group_selected_and_the_code_ignored_keeps_another_rule_of_the_group(
        self,
    ) -> None:
        #: Given
        selection = RuleSelection(select=frozenset({SAMPLE, SMP001}), ignore=frozenset({SMP001}))
        code = SMP002

        #: When
        kept = selection.is_kept(code)

        #: Then
        assert kept, 'the group selected keeps the rules the code ignored does not name'
