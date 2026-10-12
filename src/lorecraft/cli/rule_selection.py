"""Build the rule selection of one run from the typed values of `--select` and `--ignore`, against the registry.

The command line has already parsed each value into its selectors and confirmed them against the rule index
(`rule_arguments`), so this module only converts: each selector turns itself into the rule-side `AllRules`,
`RuleGroup`, `RuleCodePrefix` or `RuleCode`, and the registry holds each group and code, since `just gen-check` holds
the index equal to it. An alias code resolves to its rule's code with a warning naming the code to write.

What a selection cannot do is warned of on stderr, and the run goes on.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

import typer

from lorecraft.rules.declaration import Rule, RuleCode
from lorecraft.rules.registry import Registry
from lorecraft.rules.selection import AllRules, RuleSelection, RuleSelector

from .rule_arguments import AliasSelector, SelectorValue


class SelectionOption(StrEnum):
    """The option a selector was given to, as the command line spells it."""

    SELECT = '--select'
    IGNORE = '--ignore'


@dataclass(frozen=True, slots=True)
class AliasCodeSelected:
    """A selector was an alias code, which selects its rule; the run goes on, and the user learns the code to write.

    Attributes:
        option: The option the alias code was given to.
        alias: The alias code, as typed.
        code: The code of the rule it resolved to.
    """

    option: SelectionOption
    alias: str
    code: RuleCode

    def message(self) -> str:
        """Name the alias code and the code it resolved to."""
        return f'{self.option} {self.alias!r} is an alias code of {self.code}; write {self.code} instead'


@dataclass(frozen=True, slots=True)
class ParsedRuleSelection:
    """What `--select` and `--ignore` build: the selection, and each alias code they held.

    Attributes:
        selection: The rules the run keeps.
        aliases: Each alias code given, in the order typed, `--select` first.
    """

    selection: RuleSelection
    aliases: tuple[AliasCodeSelected, ...]


def build_rule_selection(
    registry: Registry, *, select: Sequence[SelectorValue] | None, ignore: Sequence[SelectorValue] | None
) -> ParsedRuleSelection:
    """Build the selection of one run from the values of `--select` and `--ignore`.

    Args:
        registry: Every rule, which holds each group and code the values name.
        select: Each value `--select` was given, or None when it was not, which selects every rule.
        ignore: Each value `--ignore` was given, or None when it was not, which ignores none.

    Raises:
        RuntimeError: If a value names a group or a code the registry does not hold, which the rule index held: the
            index is stale.
    """
    selected: frozenset[RuleSelector] = frozenset({AllRules()})
    select_aliases: tuple[AliasCodeSelected, ...] = ()
    if select is not None:
        select_selectors, select_aliases = _convert_values(registry, SelectionOption.SELECT, select)
        selected = frozenset(select_selectors)
    ignored: frozenset[RuleSelector] = frozenset()
    ignore_aliases: tuple[AliasCodeSelected, ...] = ()
    if ignore is not None:
        ignore_selectors, ignore_aliases = _convert_values(registry, SelectionOption.IGNORE, ignore)
        ignored = frozenset(ignore_selectors)
    return ParsedRuleSelection(RuleSelection(select=selected, ignore=ignored), select_aliases + ignore_aliases)


def _convert_values(
    registry: Registry, option: SelectionOption, values: Sequence[SelectorValue]
) -> tuple[tuple[RuleSelector, ...], tuple[AliasCodeSelected, ...]]:
    """Convert every selector of an option's values, in the order typed, with each alias code among them.

    Args:
        registry: Every rule, which holds each group and code the values name.
        option: The option the values were given to, named in a warning.
        values: Each value the option was given.
    """
    selectors: list[RuleSelector] = []
    aliases: list[AliasCodeSelected] = []
    for value in values:
        for selector in value.selectors:
            if isinstance(selector, AliasSelector):
                aliases.append(AliasCodeSelected(option, selector.alias, selector.code.to_rule_code(registry)))
            selectors.append(selector.to_rule_selector(registry))
    return tuple(selectors), tuple(aliases)


def print_selection_warnings(parsed: ParsedRuleSelection, left_off: tuple[type[Rule], ...]) -> None:
    """Warn on stderr of each alias code the selection held, then of each selected rule its level leaves off.

    A warning concerns the command line, not a subject, so it is no diagnostic: it never reaches stdout, where the
    JSON format prints one document.

    Args:
        parsed: The selection built from `--select` and `--ignore`, with each alias code they held.
        left_off: Each rule the selection names by its code that does not run, since its level is `allow`.
    """
    for alias in parsed.aliases:
        typer.echo(f'warning: {alias.message()}', err=True)
    for rule_class in left_off:
        typer.echo(
            f'warning: {rule_class.CODE} {rule_class.NAME} is selected but does not run: its level is allow, and a '
            'selection never changes a level',
            err=True,
        )
