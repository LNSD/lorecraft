"""Building a rule selection from the typed values of `--select` and `--ignore`, against a registry of sample rules."""

from typing import Final

import pytest

from lorecraft.rules.identity import RuleCode
from lorecraft.rules.registry import Registry
from lorecraft.rules.selection import AllRules, RuleSelection
from lorecraft.rules.tests.sample_rules import valid as valid_rules
from lorecraft.rules.tests.sample_rules.groups import SAMPLE
from lorecraft.rules.tests.sample_rules.valid.outline.empty_line import EmptyLine

from ..rule_arguments import (
    AliasSelector,
    AllSelector,
    CodeSelector,
    SelectorValue,
)
from ..rule_selection import (
    AliasCodeSelected,
    ParsedRuleSelection,
    SelectionOption,
    build_rule_selection,
    print_selection_warnings,
)

SMP001: Final[RuleCode] = RuleCode(SAMPLE, 1)
SMP002: Final[RuleCode] = RuleCode(SAMPLE, 2)

EVERY_RULE: Final[RuleSelection] = RuleSelection(select=frozenset({AllRules()}), ignore=frozenset())
"""The selection of a run given neither `--select` nor `--ignore`: every rule is kept."""


@pytest.fixture(scope='module')
def registry() -> Registry:
    """The valid sample rules: `SMP001` at allow, `SMP002` with the alias code `MD009`, `SMP003` removed, `LAYS001`."""
    return Registry.load(valid_rules)


@pytest.mark.unit
class TestBuildRuleSelection:
    def test_build_rule_selection_without_either_option_selects_every_rule(self, registry: Registry) -> None:
        #: Given
        select = None

        #: When
        parsed = build_rule_selection(registry, select=select, ignore=None)

        #: Then
        assert parsed == ParsedRuleSelection(EVERY_RULE, ()), 'no option keeps every rule, and warns of nothing'

    def test_build_rule_selection_with_a_full_code_selects_that_rule(self, registry: Registry) -> None:
        #: Given
        select = [SelectorValue((CodeSelector('SMP002'),))]

        #: When
        parsed = build_rule_selection(registry, select=select, ignore=None)

        #: Then
        assert parsed.selection == RuleSelection(select=frozenset({SMP002}), ignore=frozenset()), (
            'a full code converts to the rule-side code'
        )

    def test_build_rule_selection_with_repeated_values_selects_each_selector(self, registry: Registry) -> None:
        #: Given
        select = [
            SelectorValue((CodeSelector('SMP001'), CodeSelector('SMP002'))),
        ]

        #: When
        parsed = build_rule_selection(registry, select=select, ignore=None)

        #: Then
        assert parsed.selection.select == frozenset({SMP001, SMP002}), 'the selectors of every value add up'

    def test_build_rule_selection_with_only_ignore_selects_every_rule_but_the_ignored(self, registry: Registry) -> None:
        #: Given
        ignore = [SelectorValue((CodeSelector('SMP001'),))]

        #: When
        parsed = build_rule_selection(registry, select=None, ignore=ignore)

        #: Then
        assert parsed.selection == RuleSelection(select=frozenset({AllRules()}), ignore=frozenset({SMP001})), (
            'an ignore alone leaves every rule selected except the exact code'
        )

    def test_build_rule_selection_with_all_selected_and_ignored_converts_all_in_both(self, registry: Registry) -> None:
        #: Given
        values = [SelectorValue((AllSelector(),))]

        #: When
        parsed = build_rule_selection(registry, select=values, ignore=values)

        #: Then
        assert parsed == ParsedRuleSelection(
            RuleSelection(select=frozenset({AllRules()}), ignore=frozenset({AllRules()})), ()
        ), 'ALL is the selector for every rule, in either option'

    def test_build_rule_selection_with_an_alias_code_selects_its_rule_and_records_the_alias(
        self, registry: Registry
    ) -> None:
        #: Given
        select = [SelectorValue((AliasSelector('MD009', CodeSelector('SMP002')),))]

        #: When
        parsed = build_rule_selection(registry, select=select, ignore=None)

        #: Then
        assert parsed == ParsedRuleSelection(
            RuleSelection(select=frozenset({SMP002}), ignore=frozenset()),
            (AliasCodeSelected(SelectionOption.SELECT, 'MD009', SMP002),),
        ), 'an alias code converts to its rule, and the selection records it to be warned of'

    def test_build_rule_selection_with_an_alias_code_ignored_records_it_under_ignore(self, registry: Registry) -> None:
        #: Given
        ignore = [SelectorValue((AliasSelector('MD009', CodeSelector('SMP002')),))]

        #: When
        parsed = build_rule_selection(registry, select=None, ignore=ignore)

        #: Then
        assert parsed.aliases == (AliasCodeSelected(SelectionOption.IGNORE, 'MD009', SMP002),), (
            'the alias code is recorded under the option it was given to'
        )


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
