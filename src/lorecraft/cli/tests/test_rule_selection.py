"""Parsing `--select` and `--ignore` into a rule selection, against a registry of sample rules."""

from typing import Final

import pytest

from lorecraft.checks import AllRules, RuleCodePrefix, RuleSelection
from lorecraft.rules.declaration import RuleCode
from lorecraft.rules.registry import Registry
from lorecraft.rules.tests.sample_rules import token_count
from lorecraft.rules.tests.sample_rules import valid as valid_rules
from lorecraft.rules.tests.sample_rules.duplicate_name.shared import Retired
from lorecraft.rules.tests.sample_rules.groups import LAYOUT, SAMPLE
from lorecraft.rules.tests.sample_rules.valid.outline.empty_line import EmptyLine
from lorecraft.rules.tests.sample_rules.valid.retired import TabIndent

from ..rule_selection import (
    AliasCodeSelected,
    EmptySelectorError,
    EngineSelectorError,
    ParsedRuleSelection,
    RemovedRuleSelectorError,
    RuleNameSelectorError,
    SelectionOption,
    UnknownSelectorError,
    parse_rule_selection,
    print_selection_warnings,
)

SMP001: Final[RuleCode] = RuleCode(SAMPLE, 1)
SMP002: Final[RuleCode] = RuleCode(SAMPLE, 2)
LAYS001: Final[RuleCode] = RuleCode(LAYOUT, 1)

EVERY_RULE: Final[RuleSelection] = RuleSelection(select=frozenset({AllRules()}), ignore=frozenset())
"""The selection of a run given neither `--select` nor `--ignore`: every rule is kept."""


@pytest.fixture(scope='module')
def registry() -> Registry:
    """The valid sample rules: `SMP001` at allow, `SMP002` with the alias code `MD009`, `SMP003` removed, `LAYS001`."""
    return Registry.load(valid_rules)


@pytest.mark.unit
class TestParseRuleSelection:
    def test_parse_rule_selection_without_either_option_selects_every_rule(self, registry: Registry) -> None:
        #: Given
        select = None

        #: When
        parsed = parse_rule_selection(registry, select=select, ignore=None)

        #: Then
        assert parsed == ParsedRuleSelection(EVERY_RULE, ()), 'no option keeps every rule, and warns of nothing'

    def test_parse_rule_selection_with_a_code_and_a_prefix_selects_both(self, registry: Registry) -> None:
        #: Given
        select = ['SMP002', 'LAYS']

        #: When
        parsed = parse_rule_selection(registry, select=select, ignore=None)

        #: Then
        assert parsed.selection == RuleSelection(select=frozenset({SMP002, LAYOUT}), ignore=frozenset()), (
            'a code parses to the code, and a prefix to its group'
        )

    def test_parse_rule_selection_with_comma_separated_and_repeated_values_selects_each_selector(
        self, registry: Registry
    ) -> None:
        #: Given
        select = [' SMP001 , SMP002', 'LAYS001']

        #: When
        parsed = parse_rule_selection(registry, select=select, ignore=None)

        #: Then
        assert parsed.selection.select == frozenset({SMP001, SMP002, LAYS001}), (
            'each value splits at its commas, each selector stripped, and repeated values add up'
        )

    def test_parse_rule_selection_with_only_ignore_selects_every_rule_but_the_ignored(self, registry: Registry) -> None:
        #: Given
        ignore = ['SMP']

        #: When
        parsed = parse_rule_selection(registry, select=None, ignore=ignore)

        #: Then
        assert parsed.selection == RuleSelection(select=frozenset({AllRules()}), ignore=frozenset({SAMPLE})), (
            'an ignore alone leaves every rule selected, and names what is left out'
        )

    def test_parse_rule_selection_with_all_selected_and_ignored_parses_all_in_both(self, registry: Registry) -> None:
        #: Given
        selector = ['ALL']

        #: When
        parsed = parse_rule_selection(registry, select=selector, ignore=selector)

        #: Then
        assert parsed == ParsedRuleSelection(
            RuleSelection(select=frozenset({AllRules()}), ignore=frozenset({AllRules()})), ()
        ), 'ALL is the selector for every rule, in either option'

    def test_parse_rule_selection_with_a_lowercase_all_raises_unknown_selector_error(self, registry: Registry) -> None:
        #: Given
        select = ['all']

        #: When
        with pytest.raises(UnknownSelectorError) as exc_info:
            parse_rule_selection(registry, select=select, ignore=None)

        #: Then
        assert exc_info.value.selector == 'all', 'ALL is matched as spelled'

    def test_parse_rule_selection_with_code_prefixes_of_one_and_two_digits_parses_each(
        self, registry: Registry
    ) -> None:
        #: Given
        select = ['SMP0', 'SMP00']

        #: When
        parsed = parse_rule_selection(registry, select=select, ignore=None)

        #: Then
        assert parsed.selection.select == frozenset({RuleCodePrefix(SAMPLE, '0'), RuleCodePrefix(SAMPLE, '00')}), (
            'a group prefix and one or two digits starting a rule in service parse to a code prefix'
        )

    def test_parse_rule_selection_with_a_code_prefix_starting_no_rule_raises_unknown_selector_error(
        self, registry: Registry
    ) -> None:
        #: Given
        ignore = ['SMP1']

        #: When
        with pytest.raises(UnknownSelectorError) as exc_info:
            parse_rule_selection(registry, select=None, ignore=ignore)

        #: Then
        assert exc_info.value.option == SelectionOption.IGNORE, 'the error names the option the prefix was given to'
        assert exc_info.value.selector == 'SMP1', 'a code prefix no rule in service starts is unknown'

    def test_parse_rule_selection_with_four_digits_raises_unknown_selector_error(self, registry: Registry) -> None:
        #: Given
        select = ['SMP0000']

        #: When
        with pytest.raises(UnknownSelectorError) as exc_info:
            parse_rule_selection(registry, select=select, ignore=None)

        #: Then
        assert exc_info.value.selector == 'SMP0000', 'more digits than a code holds is no code nor prefix'

    def test_parse_rule_selection_with_a_letter_after_the_prefix_raises_unknown_selector_error(
        self, registry: Registry
    ) -> None:
        #: Given
        select = ['SMPx']

        #: When
        with pytest.raises(UnknownSelectorError) as exc_info:
            parse_rule_selection(registry, select=select, ignore=None)

        #: Then
        assert exc_info.value.selector == 'SMPx', 'a prefix is followed by digits only'

    def test_parse_rule_selection_with_a_lowercase_code_prefix_raises_unknown_selector_error(
        self, registry: Registry
    ) -> None:
        #: Given
        select = ['smp0']

        #: When
        with pytest.raises(UnknownSelectorError) as exc_info:
            parse_rule_selection(registry, select=select, ignore=None)

        #: Then
        assert exc_info.value.selector == 'smp0', 'a code prefix is matched as spelled'

    def test_parse_rule_selection_with_an_alias_code_selects_its_rule_and_records_the_alias(
        self, registry: Registry
    ) -> None:
        #: Given
        select = ['MD009']

        #: When
        parsed = parse_rule_selection(registry, select=select, ignore=None)

        #: Then
        assert parsed == ParsedRuleSelection(
            RuleSelection(select=frozenset({SMP002}), ignore=frozenset()),
            (AliasCodeSelected(SelectionOption.SELECT, 'MD009', SMP002),),
        ), 'an alias code resolves to its rule, and the selection records it to be warned of'

    def test_parse_rule_selection_with_an_alias_code_ignored_records_it_under_ignore(self, registry: Registry) -> None:
        #: Given
        ignore = ['MD009']

        #: When
        parsed = parse_rule_selection(registry, select=None, ignore=ignore)

        #: Then
        assert parsed.aliases == (AliasCodeSelected(SelectionOption.IGNORE, 'MD009', SMP002),), (
            'the alias code is recorded under the option it was given to'
        )

    def test_parse_rule_selection_with_a_trailing_comma_raises_empty_selector_error(self, registry: Registry) -> None:
        #: Given
        select = ['SMP002,']

        #: When
        with pytest.raises(EmptySelectorError) as exc_info:
            parse_rule_selection(registry, select=select, ignore=None)

        #: Then
        assert exc_info.value.option == SelectionOption.SELECT, 'the error names the option the value was given to'
        assert exc_info.value.value == 'SMP002,', 'the error names the value as typed'

    def test_parse_rule_selection_with_an_unknown_code_raises_unknown_selector_error(self, registry: Registry) -> None:
        #: Given
        ignore = ['SMP999']

        #: When
        with pytest.raises(UnknownSelectorError) as exc_info:
            parse_rule_selection(registry, select=None, ignore=ignore)

        #: Then
        assert exc_info.value.option == SelectionOption.IGNORE, 'the error names the option the selector was given to'
        assert exc_info.value.selector == 'SMP999', 'the error names the selector no rule has'

    def test_parse_rule_selection_with_a_lowercase_prefix_raises_unknown_selector_error(
        self, registry: Registry
    ) -> None:
        #: Given
        select = ['smp']

        #: When
        with pytest.raises(UnknownSelectorError) as exc_info:
            parse_rule_selection(registry, select=select, ignore=None)

        #: Then
        assert exc_info.value.selector == 'smp', 'a prefix is matched as spelled'

    def test_parse_rule_selection_with_a_rule_name_raises_rule_name_selector_error(self, registry: Registry) -> None:
        #: Given
        select = ['trailing-space']

        #: When
        with pytest.raises(RuleNameSelectorError) as exc_info:
            parse_rule_selection(registry, select=select, ignore=None)

        #: Then
        assert exc_info.value.selector == 'trailing-space', 'the error names the rule name typed'
        assert exc_info.value.code == SMP002, 'the error carries the code to write instead'
        assert 'SMP002' in str(exc_info.value), 'the message names the code to write instead'

    def test_parse_rule_selection_with_a_removed_code_raises_removed_rule_selector_error(
        self, registry: Registry
    ) -> None:
        #: Given
        select = ['SMP003']

        #: When
        with pytest.raises(RemovedRuleSelectorError) as exc_info:
            parse_rule_selection(registry, select=select, ignore=None)

        #: Then
        assert exc_info.value.removed_rule is TabIndent, 'the error carries the removed rule'
        assert '1.3.0' in str(exc_info.value), 'the message names the release that removed the rule'
        assert 'select SMP002 instead' in str(exc_info.value), 'the message names the code that replaced it'

    def test_parse_rule_selection_with_a_removed_code_nothing_replaced_says_so(self) -> None:
        #: Given
        registry = Registry((Retired,))

        #: When
        with pytest.raises(RemovedRuleSelectorError) as exc_info:
            parse_rule_selection(registry, select=None, ignore=['SMP002'])

        #: Then
        assert exc_info.value.removed_rule is Retired, 'the error carries the removed rule'
        assert 'no rule replaces it' in str(exc_info.value), 'a removed rule with no replacement is named as such'

    def test_parse_rule_selection_with_an_engine_condition_code_raises_engine_selector_error(self) -> None:
        #: Given
        registry = Registry.load(token_count)

        #: When
        with pytest.raises(EngineSelectorError) as exc_info:
            parse_rule_selection(registry, select=None, ignore=['LC900'])

        #: Then
        assert exc_info.value.option == SelectionOption.IGNORE, 'the error names the option the code was given to'
        assert exc_info.value.selector == 'LC900', "an engine condition's code cannot be ignored"

    def test_parse_rule_selection_with_the_engine_prefix_raises_engine_selector_error(self) -> None:
        #: Given
        registry = Registry.load(token_count)

        #: When
        with pytest.raises(EngineSelectorError) as exc_info:
            parse_rule_selection(registry, select=['LC'], ignore=None)

        #: Then
        assert exc_info.value.option == SelectionOption.SELECT, 'the error names the option the prefix was given to'
        assert exc_info.value.selector == 'LC', "the engine group's prefix cannot be selected"

    def test_parse_rule_selection_with_an_engine_code_prefix_raises_engine_selector_error(self) -> None:
        #: Given
        registry = Registry.load(token_count)

        #: When
        with pytest.raises(EngineSelectorError) as exc_info:
            parse_rule_selection(registry, select=['LC9'], ignore=None)

        #: Then
        assert exc_info.value.selector == 'LC9', 'a prefix of engine condition codes cannot be selected'


@pytest.mark.unit
class TestPrintSelectionWarnings:
    def test_print_selection_warnings_with_an_alias_and_a_rule_left_off_warns_of_each_on_stderr(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        #: Given
        parsed = ParsedRuleSelection(
            RuleSelection(select=frozenset({SMP001, SMP002}), ignore=frozenset()),
            (AliasCodeSelected(SelectionOption.SELECT, 'MD009', SMP002),),
        )

        #: When
        print_selection_warnings(parsed, (EmptyLine,))

        #: Then
        captured = capsys.readouterr()
        assert captured.out == '', 'a warning never reaches stdout, where the JSON format prints one document'
        assert captured.err == (
            "warning: --select 'MD009' is an alias code of SMP002; write SMP002 instead\n"
            'warning: SMP001 empty-line is selected but does not run: its level is allow, and a selection never '
            'changes a level\n'
        ), 'the alias code is warned of first, then the rule its level leaves off'

    def test_print_selection_warnings_with_nothing_to_warn_of_prints_nothing(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        #: Given
        parsed = ParsedRuleSelection(EVERY_RULE, ())

        #: When
        print_selection_warnings(parsed, ())

        #: Then
        captured = capsys.readouterr()
        assert captured.out == '', 'nothing reaches stdout'
        assert captured.err == '', 'a selection with nothing to warn of prints no warning'
