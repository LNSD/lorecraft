"""Parse `--select` and `--ignore` into the rule selection of one run, against the registry.

Each value an option is given holds one or more selectors separated by commas, whitespace around each stripped. A
selector is, as in ruff, `ALL`, a group's prefix, such as `OUT`, a prefix of a code with one or two of its digits,
such as `OUT0`, a rule's code, such as `OUT006`, or an alias code, which resolves to its rule's code with a warning
naming the code to write. Selectors are matched as spelled, so `out` is unknown. Nothing past this module reads a
selector as text: each parses to an `AllRules`, a `RuleGroup`, a `RuleCodePrefix` or a `RuleCode`, and the registry
is the authority on which exist.

A selector that cannot narrow a run is refused before any subject is checked: an empty one, one no rule or group
has, a code prefix no rule in service starts with, a rule's name, an engine condition or the engine's group, which
are always reported, and a removed rule. What a selection cannot do is warned of on stderr, and the run goes on.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from string import digits
from typing import assert_never

import typer

from lorecraft.checks import AllRules, RuleCodePrefix, RuleSelection, RuleSelector
from lorecraft.core.error import Error
from lorecraft.rules.declaration import ALL_RULES_SELECTOR, EngineCondition, RemovedRule, Rule, RuleCode, RuleGroup
from lorecraft.rules.registry import Registry


class SelectionOption(StrEnum):
    """The option a selector was given to, as the command line spells it."""

    SELECT = '--select'
    IGNORE = '--ignore'


class EmptySelectorError(Error):
    """A value of `--select` or `--ignore` holds an empty selector, such as one left by a trailing comma.

    Attributes:
        option: The option the value was given to, `--select` or `--ignore`.
        value: The value as typed.
    """

    option: SelectionOption
    value: str

    def __init__(self, option: SelectionOption, value: str) -> None:
        self.option = option
        self.value = value
        super().__init__(f'{option} {value!r} holds an empty selector')


class UnknownSelectorError(Error):
    """A selector is not `ALL`, nor a code, an alias code, a group prefix or a code prefix the registry holds.

    Attributes:
        option: The option the selector was given to.
        selector: The selector as typed, whitespace stripped.
    """

    option: SelectionOption
    selector: str

    def __init__(self, option: SelectionOption, selector: str) -> None:
        self.option = option
        self.selector = selector
        super().__init__(f'{option} {selector!r} is no rule code or prefix')


class RuleNameSelectorError(Error):
    """A selector is a rule's name, which selects nothing: a rule is selected by its code.

    Attributes:
        option: The option the selector was given to.
        selector: The rule's name, as typed.
        code: The code of the rule it names, the selector to write instead.
    """

    option: SelectionOption
    selector: str
    code: RuleCode

    def __init__(self, option: SelectionOption, selector: str, code: RuleCode) -> None:
        self.option = option
        self.selector = selector
        self.code = code
        super().__init__(f'{option} {selector!r} is a rule name; select the rule by its code, {code}')


class EngineSelectorError(Error):
    """A selector names an engine condition or the engine's group, which every run reports and none can filter.

    Attributes:
        option: The option the selector was given to.
        selector: The condition's code or name, or the engine's prefix, as typed.
    """

    option: SelectionOption
    selector: str

    def __init__(self, option: SelectionOption, selector: str) -> None:
        self.option = option
        self.selector = selector
        super().__init__(
            f'{option} {selector!r} names engine conditions, which are always reported and cannot be selected or '
            'ignored'
        )


class RemovedRuleSelectorError(Error):
    """A selector names a removed rule, which no run has.

    Attributes:
        option: The option the selector was given to.
        selector: The removed rule's code or name, as typed.
        removed_rule: The removed rule, which names the release that removed it and the rule that replaced it.
    """

    option: SelectionOption
    selector: str
    removed_rule: type[RemovedRule]

    def __init__(self, option: SelectionOption, selector: str, removed_rule: type[RemovedRule]) -> None:
        self.option = option
        self.selector = selector
        self.removed_rule = removed_rule
        replaced_by = removed_rule.REPLACED_BY
        if replaced_by is None:
            instead = 'no rule replaces it'
        else:
            instead = f'select {replaced_by} instead'
        super().__init__(
            f'{option} {selector!r} names {removed_rule.CODE}, removed in {removed_rule.REMOVED_IN}; {instead}'
        )


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
    """What `--select` and `--ignore` parse to: the selection, and each alias code they held.

    Attributes:
        selection: The rules the run keeps.
        aliases: Each alias code given, in the order typed, `--select` first.
    """

    selection: RuleSelection
    aliases: tuple[AliasCodeSelected, ...]


def parse_rule_selection(
    registry: Registry, *, select: Sequence[str] | None, ignore: Sequence[str] | None
) -> ParsedRuleSelection:
    """Parse the values of `--select` and `--ignore` into the selection of one run.

    Args:
        registry: Every rule, removed rule and engine condition, the authority on which selectors exist.
        select: Each value `--select` was given, or None when it was not, which selects every rule.
        ignore: Each value `--ignore` was given, or None when it was not, which ignores none.

    Raises:
        EmptySelectorError: If a value holds an empty selector.
        UnknownSelectorError: If a selector is no code, alias code or prefix the registry holds.
        RuleNameSelectorError: If a selector is a rule's name.
        EngineSelectorError: If a selector names an engine condition or the engine's group.
        RemovedRuleSelectorError: If a selector names a removed rule.
    """
    selected: frozenset[RuleSelector] = frozenset({AllRules()})
    select_aliases: tuple[AliasCodeSelected, ...] = ()
    if select is not None:
        select_selectors, select_aliases = _parse_values(registry, SelectionOption.SELECT, select)
        selected = frozenset(select_selectors)
    ignored: frozenset[RuleSelector] = frozenset()
    ignore_aliases: tuple[AliasCodeSelected, ...] = ()
    if ignore is not None:
        ignore_selectors, ignore_aliases = _parse_values(registry, SelectionOption.IGNORE, ignore)
        ignored = frozenset(ignore_selectors)
    return ParsedRuleSelection(RuleSelection(select=selected, ignore=ignored), select_aliases + ignore_aliases)


def _parse_values(
    registry: Registry, option: SelectionOption, values: Sequence[str]
) -> tuple[tuple[RuleSelector, ...], tuple[AliasCodeSelected, ...]]:
    """Parse every selector of an option's values, in the order typed, with each alias code among them.

    Args:
        registry: The authority on which selectors exist.
        option: The option the values were given to, named in a failure or a warning.
        values: Each value the option was given, one or more selectors separated by commas.

    Raises:
        EmptySelectorError: If a value holds an empty selector.
        UnknownSelectorError: If a selector is no code, alias code or prefix the registry holds.
        RuleNameSelectorError: If a selector is a rule's name.
        EngineSelectorError: If a selector names an engine condition or the engine's group.
        RemovedRuleSelectorError: If a selector names a removed rule.
    """
    selectors: list[RuleSelector] = []
    aliases: list[AliasCodeSelected] = []
    for value in values:
        for part in value.split(','):
            text = part.strip()
            if not text:
                raise EmptySelectorError(option, value)
            selector = _parse_selector(registry, option, text)
            match selector:
                case RuleCode():
                    # A rule's name is refused, so a code that does not print as the text typed was reached by an
                    # alias code.
                    if str(selector) != text:
                        aliases.append(AliasCodeSelected(option, text, selector))
                case AllRules() | RuleGroup() | RuleCodePrefix():
                    pass
                case _:
                    assert_never(selector)
            selectors.append(selector)
    return tuple(selectors), tuple(aliases)


def _parse_selector(registry: Registry, option: SelectionOption, text: str) -> RuleSelector:
    """Parse one selector into every rule, the rule it names, or the group or code prefix it is.

    `ALL` is read first, so it never reaches the registry. A declaration is looked up next, then a group or a code
    prefix, so a selector that is both, which no code's form allows, would be read as the declaration's.

    Args:
        registry: The authority on which selectors exist.
        option: The option the selector was given to, named in a failure.
        text: The selector, whitespace stripped and not empty.

    Raises:
        UnknownSelectorError: If it is no code, alias code or prefix the registry holds.
        RuleNameSelectorError: If it is a rule's name.
        EngineSelectorError: If it names an engine condition or the engine's group.
        RemovedRuleSelectorError: If it names a removed rule.
    """
    if text == ALL_RULES_SELECTOR:
        return AllRules()

    declaration = registry.find(text)
    if declaration is None:
        return _parse_prefix(registry, option, text)

    # A `match` class pattern tests an instance, not a class, so the branch on a declaration's kind is an
    # `issubclass` chain, closed by `assert_never` as the registry's own is.
    if issubclass(declaration, Rule):
        if text == str(declaration.NAME):
            raise RuleNameSelectorError(option, text, declaration.CODE)
        return declaration.CODE
    elif issubclass(declaration, RemovedRule):
        raise RemovedRuleSelectorError(option, text, declaration)
    elif issubclass(declaration, EngineCondition):
        raise EngineSelectorError(option, text)
    else:
        assert_never(declaration)


def _parse_prefix(registry: Registry, option: SelectionOption, text: str) -> RuleGroup | RuleCodePrefix:
    """Parse a selector no declaration has into the group whose prefix it is, or a prefix of some of its codes.

    The selector splits before its trailing digits: what precedes them is looked up as a group, and the digits, when
    there are any, must be one or two that start a rule in service's code.

    Args:
        registry: The authority on which groups and codes exist.
        option: The option the selector was given to, named in a failure.
        text: The selector, whitespace stripped, neither `ALL` nor any declaration's code, name or alias code.

    Raises:
        UnknownSelectorError: If no group has the prefix, or the digits start no rule in service's code.
        EngineSelectorError: If the prefix is the engine's group's.
    """
    group_prefix = text.rstrip(digits)
    code_digits = text[len(group_prefix) :]
    group = registry.find_group(group_prefix)
    if group is None:
        raise UnknownSelectorError(option, text)
    if registry.is_engine_group(group):
        raise EngineSelectorError(option, text)
    if not code_digits:
        return group

    # As in ruff, a code prefix is a selector only when it starts a rule's code, so a mistyped one is refused rather
    # than run as a filter that matches nothing. The text is no rule's whole code, which `find` would have returned,
    # so a text that starts one ends in the one or two digits a `RuleCodePrefix` holds.
    if not any(str(rule_class.CODE).startswith(text) for rule_class in registry.rules_in_service):
        raise UnknownSelectorError(option, text)
    return RuleCodePrefix.parse(group, code_digits)


def print_selection_warnings(parsed: ParsedRuleSelection, left_off: tuple[type[Rule], ...]) -> None:
    """Warn on stderr of each alias code the selection held, then of each selected rule its level leaves off.

    A warning concerns the command line, not a subject, so it is no diagnostic: it never reaches stdout, where the
    JSON format prints one document.

    Args:
        parsed: The selection parsed from `--select` and `--ignore`, with each alias code they held.
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
