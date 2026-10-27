"""The typed values of `--select`, parsed and confirmed while the command line is read.

A value is parsed into the form it has, and that form is confirmed against the rule index, so a command's handler is
handed a value that names something. Two ways to refuse a value are told apart: **malformed**, which has the shape of
no form the option accepts (`out`, `OUT-1`, `OUT1234`), and **unknown**, which has a shape but names nothing
(`OUT999`, `ZZZ`, `OUT9`).

These values are the command line's own, decoupled from the invariant-preserving types of `lorecraft.rules`: they
hold strings and numbers, and a conversion method with a typed argument builds the rule-side type from them when a
command runs. Parsing reads `lorecraft.rules.index` alone, which loads none of the rules engine, so this module
imports none of `lorecraft.rules.declaration`, `lorecraft.rules.subject`, `lorecraft.rules.registry`,
`lorecraft.rules.selection`, `lorecraft.project` nor `lorecraft.engine` when the command line starts. The rule-side
types are named for the checker under `TYPE_CHECKING`, and a conversion imports what it builds where it runs.

Text enters through `SelectorValue.parse`, which confirms it against the rule index. The selector
records have no `__post_init__` guard on membership: what makes one valid is the index's membership, which a guard
would have to read at every construction, and a unit test of a conversion builds one for a registry of sample rules
the index does not hold. Code builds them from `parse` alone. `CodeSelector` alone guards its number's range, which
needs no index.

A selector is `ALL`, a rule's full code such as `LC306`, or an alias code, which a rule declares: it is one
exactly when the index finds a rule for it. A rule's name, an engine condition, the engine's group and a removed
rule are refused, since none can narrow a run. `rule [RULE]` takes a code, a name or an alias code, of a rule in
service, a removed rule or an engine condition alike. Everything is matched as spelled.
"""

from dataclasses import dataclass
from string import ascii_lowercase, ascii_uppercase, digits
from typing import TYPE_CHECKING, Final, Protocol, Self

from lorecraft.core.error import Error
from lorecraft.rules import index
from lorecraft.rules.index import ConditionRow, RemovedRuleRow, RuleIndexRow

if TYPE_CHECKING:
    # Type-only: importing the rule side here would load the rules engine when the command line starts.
    from lorecraft.rules.identity import RuleCode
    from lorecraft.rules.registry import Registry
    from lorecraft.rules.selection import RuleSelector

_ALL: Final[str] = 'ALL'
"""The selector for every rule; no group may take it as its prefix."""

_NAME_CHARACTERS: Final[str] = ascii_lowercase + digits + '-'
"""What a rule's name is made of, apart from its hyphens' places."""


class EmptySelectorError(Error):
    """A value of `--select` holds an empty selector, such as one left by a trailing comma.

    Attributes:
        value: The value as typed.
    """

    value: str

    def __init__(self, value: str) -> None:
        self.value = value
        super().__init__(f'{value!r} holds an empty selector')


class MalformedSelectorError(Error):
    """A selector has the shape of no selector: not `ALL`, a group's prefix, a code prefix, a code nor an alias code.

    Attributes:
        text: The selector as typed, whitespace stripped.
    """

    text: str

    def __init__(self, text: str) -> None:
        self.text = text
        super().__init__(f'{text!r} is no selector: write ALL, a full rule code such as LC101, or an alias code')


class UnknownSelectorError(Error):
    """A selector is well formed and names nothing: no full rule code or alias code of a rule has it.

    Attributes:
        text: The selector as typed, whitespace stripped.
    """

    text: str

    def __init__(self, text: str) -> None:
        self.text = text
        super().__init__(f'{text!r} is no rule code or alias code')


class RuleNameSelectorError(Error):
    """A selector is a rule's name, which selects nothing: a rule is selected by its code.

    Attributes:
        text: The rule's name, as typed.
        code: The code of the rule it names, the selector to write instead.
    """

    text: str
    code: str

    def __init__(self, text: str, code: str) -> None:
        self.text = text
        self.code = code
        super().__init__(f'{text!r} is a rule name; select the rule by its code, {code}')


class EngineSelectorError(Error):
    """A selector names an engine condition or the engine's group, which every run reports and none can filter.

    Attributes:
        text: The condition's code or name, or the engine's prefix, as typed.
    """

    text: str

    def __init__(self, text: str) -> None:
        self.text = text
        super().__init__(f'{text!r} names engine conditions, which are always reported and cannot be selected')


class RemovedRuleSelectorError(Error):
    """A selector names a removed rule, which no run has.

    The index holds neither the release that removed a rule nor what replaced it, so the message names neither:
    `lorecraft rule` prints the removed rule's page, which does, and says so when nothing replaced it.

    Attributes:
        text: The removed rule's code or name, as typed.
        code: The removed rule's code.
    """

    text: str
    code: str

    def __init__(self, text: str, code: str) -> None:
        self.text = text
        self.code = code
        super().__init__(
            f'{text!r} names {code}, a removed rule; `lorecraft rule {code}` says when it was removed and what '
            'replaces it, if any'
        )


class IndexRuleNotInRegistryError(RuntimeError):
    """The rule index lists a rule the registry does not hold, so the generated index is out of date.

    It is a defect of the repository, not the user's input: the CI `gen-check` job holds the two equal.

    Attributes:
        key: The code, name or alias code the index found.
    """

    key: str

    def __init__(self, key: str) -> None:
        self.key = key
        super().__init__(f'the rule index lists {key!r}, which the registry does not hold: run `just gen`')


@dataclass(frozen=True, slots=True)
class AllSelector:
    """The selector `ALL`: every rule."""

    def to_rule_selector(self, registry: Registry) -> RuleSelector:
        """The rule-side selector of every rule.

        Args:
            registry: Every rule; not read, and taken so that every selector converts alike.
        """
        from lorecraft.rules.selection import AllRules

        return AllRules()

    def __str__(self) -> str:
        """The selector as typed: `ALL`."""
        return _ALL


@dataclass(frozen=True, slots=True)
class CodeSelector:
    """A full rule code confirmed by the index."""

    code: str

    def to_rule_code(self, registry: Registry) -> RuleCode:
        """The rule-side code the registry holds."""
        from lorecraft.rules.declaration import Rule

        declaration = registry.find(self.code)
        if declaration is None or not issubclass(declaration, Rule):
            raise IndexRuleNotInRegistryError(self.code)
        return declaration.CODE

    def to_rule_selector(self, registry: Registry) -> RuleSelector:
        """The rule-side code, which selects its rule."""
        return self.to_rule_code(registry)

    def __str__(self) -> str:
        """The full code as typed."""
        return self.code


@dataclass(frozen=True, slots=True)
class AliasSelector:
    """An alias code a rule declares, such as `MD040`, which selects that rule.

    Attributes:
        alias: The alias code, as typed.
        code: The code of the rule that declares it.
    """

    alias: str
    code: CodeSelector

    def to_rule_selector(self, registry: Registry) -> RuleSelector:
        """The rule-side code of the rule the alias code names.

        Args:
            registry: Every rule, which holds the group.
        """
        return self.code.to_rule_code(registry)

    def __str__(self) -> str:
        """The selector as typed: the alias code."""
        return self.alias


type RuleSelectorArgument = AllSelector | CodeSelector | AliasSelector
"""What one selector of `--select` parses to."""


class RuleIndex(Protocol):
    """What CLI argument parsing reads of the rule index: lookup by code, name or alias."""

    def find(self, key: str, /) -> RuleIndexRow | None:
        """The row whose code, name or alias code is `key`, or None when none is."""
        ...


@dataclass(frozen=True, slots=True)
class SelectorValue:
    """One value given to `--select`: the selectors it holds, in the order typed.

    Attributes:
        selectors: One or more selectors; a value is split at its commas.
    """

    selectors: tuple[RuleSelectorArgument, ...]

    @classmethod
    def parse(cls, raw: str, rule_index: RuleIndex = index) -> Self:
        """Parse one value of `--select` into its selectors, each confirmed against the rule index.

        Args:
            raw: The value as typed: one or more selectors separated by commas, whitespace around each stripped.
            rule_index: The rule index the selectors are confirmed against.

        Raises:
            EmptySelectorError: If the value holds an empty selector.
            MalformedSelectorError: If a selector has the shape of no selector.
            UnknownSelectorError: If a selector names no rule.
            RuleNameSelectorError: If a selector is a rule's name.
            EngineSelectorError: If a selector names an engine condition or the engine's group.
            RemovedRuleSelectorError: If a selector names a removed rule.
        """
        selectors: list[RuleSelectorArgument] = []
        for part in raw.split(','):
            text = part.strip()
            if not text:
                raise EmptySelectorError(raw)
            selectors.append(_parse_selector(text, rule_index))
        return cls(tuple(selectors))

    def __str__(self) -> str:
        """The selectors as typed, joined by commas."""
        return ','.join(str(selector) for selector in self.selectors)


def _parse_selector(text: str, rule_index: RuleIndex) -> RuleSelectorArgument:
    """Parse one selector, whitespace stripped and not empty.

    `ALL` is read first, then what the index finds by full code, name or alias code.

    Args:
        text: The selector as typed.
        rule_index: The rule index to read.

    Raises:
        MalformedSelectorError: If it has the shape of no selector.
        UnknownSelectorError: If it names no rule.
        RuleNameSelectorError: If it is a rule's name.
        EngineSelectorError: If it names an engine condition or the engine's group.
        RemovedRuleSelectorError: If it names a removed rule.
    """
    if text == _ALL:
        return AllSelector()
    row = rule_index.find(text)
    if row is None:
        if text and all(character in ascii_uppercase or character in digits for character in text):
            raise UnknownSelectorError(text)
        raise MalformedSelectorError(text)

    code, name = row.code, row.name
    if isinstance(row, ConditionRow):
        raise EngineSelectorError(text)
    if isinstance(row, RemovedRuleRow):
        raise RemovedRuleSelectorError(text, code)
    if text == name:
        raise RuleNameSelectorError(text, code)
    selector = CodeSelector(code)
    if text == code:
        return selector
    return AliasSelector(text, selector)


def _has_code_shape(text: str) -> bool:
    """Whether text has an uppercase prefix followed by exactly three digits."""
    split = len(text) - index.CODE_DIGITS
    return (
        split > 0
        and all(character in ascii_uppercase for character in text[:split])
        and all(character in digits for character in text[split:])
        and int(text[split:]) > 0
    )


def _has_name_shape(text: str) -> bool:
    """Whether the text has the shape of a rule's name: kebab-case, with no leading, trailing or doubled hyphen.

    Args:
        text: The word of a rule argument to classify.
    """
    if not text or any(character not in _NAME_CHARACTERS for character in text):
        return False
    return not text.startswith('-') and not text.endswith('-') and '--' not in text
