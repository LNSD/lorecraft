"""The typed values of `--select`, `--ignore` and `rule [RULE]`, parsed and confirmed while the command line is read.

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

Text enters through `SelectorValue.parse` and `RuleKey.parse`, which confirm it against the rule index. The selector
records have no `__post_init__` guard on membership: what makes one valid is the index's membership, which a guard
would have to read at every construction, and a unit test of a conversion builds one for a registry of sample rules
the index does not hold. Code builds them from `parse` alone. `CodeSelector` alone guards its number's range, which
needs no index.

A selector is, as in ruff, `ALL`, a group's prefix such as `OUT`, a prefix of a code with one or two of its digits
such as `OUT0`, a rule's code such as `OUT006`, or an alias code, which a rule declares: it is one exactly when the
index finds a rule for it. A rule's name, an engine condition, the engine's group and a removed rule are refused,
since none can narrow a run. `rule [RULE]` takes a code, a name or an alias code, of a rule in service, a removed
rule or an engine condition alike. Everything is matched as spelled.
"""

from dataclasses import dataclass
from string import ascii_lowercase, ascii_uppercase, digits
from typing import TYPE_CHECKING, Final, Literal, Protocol, Self

from lorecraft.core.error import Error
from lorecraft.rules import index

if TYPE_CHECKING:
    # Type-only: importing the rule side here would load the rules engine when the command line starts.
    from lorecraft.rules.declaration import RuleDeclaration
    from lorecraft.rules.identity import RuleCode, RuleGroup
    from lorecraft.rules.registry import Registry
    from lorecraft.rules.selection import RuleSelector

_ALL: Final[str] = 'ALL'
"""The selector for every rule; no group may take it as its prefix."""

_MAX_CODE_NUMBER: Final[int] = 10**index.CODE_DIGITS - 1
"""The largest number a code holds: the one with every digit a 9."""

_RULE_KIND: Final[str] = 'rule'
_REMOVED_KIND: Final[str] = 'removed'
_CONDITION_KIND: Final[str] = 'condition'
"""The kinds of the index's rows, as its `kind` column spells them."""

_NAME_CHARACTERS: Final[str] = ascii_lowercase + digits + '-'
"""What a rule's name is made of, apart from its hyphens' places."""


class EmptySelectorError(Error):
    """A value of `--select` or `--ignore` holds an empty selector, such as one left by a trailing comma.

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
        super().__init__(
            f'{text!r} is no selector: write ALL, a group prefix such as OUT, a code prefix such as OUT0, or a rule '
            'code such as OUT004'
        )


class CodeNumberOutOfRangeError(ValueError):
    """A code selector was built with a number outside 1 to 999, so it would not print as three digits.

    A number comes from the rule index, never from what a user types, so one outside the range is a defect in the
    code that built the selector, not a failure of the command line (error-boundaries §1).

    Attributes:
        number: The rejected number.
    """

    number: int

    def __init__(self, number: int) -> None:
        self.number = number
        super().__init__(f'number must be from 1 to {_MAX_CODE_NUMBER}, got {number}')


class UnknownSelectorError(Error):
    """A selector is well formed and names nothing: no group, code prefix, code nor alias code of a rule has it.

    Attributes:
        text: The selector as typed, whitespace stripped.
    """

    text: str

    def __init__(self, text: str) -> None:
        self.text = text
        super().__init__(f'{text!r} is no rule code or prefix')


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
        super().__init__(
            f'{text!r} names engine conditions, which are always reported and cannot be selected or ignored'
        )


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


class IndexGroupNotInRegistryError(RuntimeError):
    """The rule index lists a group the registry does not hold, so the generated index is out of date.

    It is a defect of the repository, not the user's input: the CI `gen-check` job holds the two equal.

    Attributes:
        prefix: The group's prefix, which the index lists.
    """

    prefix: str

    def __init__(self, prefix: str) -> None:
        self.prefix = prefix
        super().__init__(f'the rule index lists group {prefix!r}, which the registry does not hold: run `just gen`')


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


class MalformedRuleKeyError(Error):
    """A rule key has the shape of neither a rule's code nor a rule's name, and is no alias code a rule declares.

    Attributes:
        text: The key as typed.
    """

    text: str

    def __init__(self, text: str) -> None:
        self.text = text
        super().__init__(
            f'{text!r} is no rule code, name or alias code: write a code such as OUT004 or a name such as empty-section'
        )


class UnknownRuleKeyError(Error):
    """A rule key is well formed and names nothing: no rule, removed rule or engine condition has it.

    Attributes:
        text: The key as typed.
    """

    text: str

    def __init__(self, text: str) -> None:
        self.text = text
        super().__init__(f'no rule has the code, name or alias code {text!r}')


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
class GroupSelector:
    """A group's prefix, such as `OUT`: every rule of the group.

    Attributes:
        prefix: The group's prefix, which the index has.
    """

    prefix: str

    def to_rule_selector(self, registry: Registry) -> RuleSelector:
        """The rule-side group this prefix names.

        Args:
            registry: Every rule, which holds the group.
        """
        return _require_group(registry, self.prefix)

    def __str__(self) -> str:
        """The selector as typed: the group's prefix."""
        return self.prefix


@dataclass(frozen=True, slots=True)
class CodePrefixSelector:
    """The start of some codes of one group, such as `OUT0`: a group's prefix and one or two of a code's digits.

    Attributes:
        group_prefix: The prefix of the group whose codes it starts, which the index has.
        digits: One or two ASCII digits that start the code of a rule in service.
    """

    group_prefix: str
    digits: str

    def to_rule_selector(self, registry: Registry) -> RuleSelector:
        """The rule-side code prefix.

        Args:
            registry: Every rule, which holds the group.
        """
        from lorecraft.rules.selection import RuleCodePrefix

        return RuleCodePrefix(_require_group(registry, self.group_prefix), self.digits)

    def __str__(self) -> str:
        """The selector as typed: the group's prefix, then the digits."""
        return f'{self.group_prefix}{self.digits}'


@dataclass(frozen=True, slots=True)
class CodeSelector:
    """A rule's code, such as `OUT006`: its group's prefix and its number.

    Attributes:
        group_prefix: The prefix of the rule's group.
        number: The rule's number in its group, from 1 to 999.
    """

    group_prefix: str
    number: int

    def __post_init__(self) -> None:
        """Reject a number that would not print as three digits.

        Raises:
            CodeNumberOutOfRangeError: If the number is outside 1 to 999.
        """
        if not 1 <= self.number <= _MAX_CODE_NUMBER:
            raise CodeNumberOutOfRangeError(self.number)

    def to_rule_code(self, registry: Registry) -> RuleCode:
        """The rule-side code.

        Args:
            registry: Every rule, which holds the group.
        """
        from lorecraft.rules.identity import RuleCode

        return RuleCode(_require_group(registry, self.group_prefix), self.number)

    def to_rule_selector(self, registry: Registry) -> RuleSelector:
        """The rule-side code, which selects its rule.

        Args:
            registry: Every rule, which holds the group.
        """
        return self.to_rule_code(registry)

    def __str__(self) -> str:
        """The selector as typed: the group's prefix, then the number zero-padded to three digits."""
        return f'{self.group_prefix}{self.number:0{index.CODE_DIGITS}d}'


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


type RuleSelectorArgument = AllSelector | GroupSelector | CodePrefixSelector | CodeSelector | AliasSelector
"""What one selector of `--select` or `--ignore` parses to."""


class RuleIndex(Protocol):
    """What parsing reads of the rule index: `lorecraft.rules.index` is one, and a unit test passes a small table."""

    @property
    def CODE_DIGITS(self) -> int:  # noqa: N802
        """How many digits end a code, after its group's prefix."""
        ...

    @property
    def RULES(self) -> tuple[tuple[str, str, Literal['rule', 'removed', 'condition'], str, tuple[str, ...]], ...]:  # noqa: N802
        """Every rule's code, name, kind, level or severity, and alias codes."""
        ...

    def find(
        self, key: str, /
    ) -> tuple[str, str, Literal['rule', 'removed', 'condition'], str, tuple[str, ...]] | None:
        """The row whose code, name or alias code is `key`, or None when none is."""
        ...

    def find_group_title(self, prefix: str, /) -> str | None:
        """The title of the group with this prefix, or None when none has it."""
        ...


@dataclass(frozen=True, slots=True)
class SelectorValue:
    """One value given to `--select` or `--ignore`: the selectors it holds, in the order typed.

    Attributes:
        selectors: One or more selectors; a value is split at its commas.
    """

    selectors: tuple[RuleSelectorArgument, ...]

    @classmethod
    def parse(cls, raw: str, rule_index: RuleIndex = index) -> Self:
        """Parse one value of `--select` or `--ignore` into its selectors, each confirmed against the rule index.

        Args:
            raw: The value as typed: one or more selectors separated by commas, whitespace around each stripped.
            rule_index: The rule index the selectors are confirmed against.

        Raises:
            EmptySelectorError: If the value holds an empty selector.
            MalformedSelectorError: If a selector has the shape of no selector.
            UnknownSelectorError: If a selector is well formed and names nothing.
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


@dataclass(frozen=True, slots=True)
class RuleKey:
    """The argument of `rule [RULE]`: a rule's code, its name or an alias code, which the index has.

    Attributes:
        text: The key as typed.
    """

    text: str

    @classmethod
    def parse(cls, raw: str, rule_index: RuleIndex = index) -> Self:
        """Parse the argument of `rule [RULE]`, confirmed against the rule index.

        An alias code has no shape of its own: it is one exactly when the index finds a rule for it.

        Args:
            raw: The argument as typed.
            rule_index: The rule index the key is confirmed against.

        Raises:
            MalformedRuleKeyError: If it has the shape of neither a code nor a name, and no rule declares it as an
                alias code.
            UnknownRuleKeyError: If it is shaped as a code or a name, and no rule has it.
        """
        if rule_index.find(raw) is not None:
            return cls(raw)
        if _has_code_shape(raw, rule_index) or _has_name_shape(raw):
            raise UnknownRuleKeyError(raw)
        raise MalformedRuleKeyError(raw)

    def to_declaration(self, registry: Registry) -> RuleDeclaration:
        """The rule, removed rule or engine condition the key names.

        Args:
            registry: Every rule, which holds the declaration.

        Raises:
            IndexRuleNotInRegistryError: If the registry has no declaration for the key, which the index held.
        """
        declaration = registry.find(self.text)
        if declaration is None:
            raise IndexRuleNotInRegistryError(self.text)
        return declaration

    def __str__(self) -> str:
        """The key as typed."""
        return self.text


def _parse_selector(text: str, rule_index: RuleIndex) -> RuleSelectorArgument:
    """Parse one selector, whitespace stripped and not empty.

    `ALL` is read first, then what the index finds by code, name or alias code, and last the shapes of a group and of
    a code prefix, which the index cannot find.

    Args:
        text: The selector as typed.
        rule_index: The rule index to read.

    Raises:
        MalformedSelectorError: If it has the shape of no selector.
        UnknownSelectorError: If it is well formed and names nothing.
        RuleNameSelectorError: If it is a rule's name.
        EngineSelectorError: If it names an engine condition or the engine's group.
        RemovedRuleSelectorError: If it names a removed rule.
    """
    if text == _ALL:
        return AllSelector()
    row = rule_index.find(text)
    if row is None:
        return _parse_prefix(text, rule_index)

    code, name, kind, _level, _aliases = row
    if kind == _CONDITION_KIND:
        raise EngineSelectorError(text)
    if kind == _REMOVED_KIND:
        raise RemovedRuleSelectorError(text, code)
    if text == name:
        raise RuleNameSelectorError(text, code)
    selector = _split_code(code, rule_index)
    if text == code:
        return selector
    return AliasSelector(text, selector)


def _parse_prefix(text: str, rule_index: RuleIndex) -> GroupSelector | CodePrefixSelector:
    """Parse a selector the index has no rule for into a group's prefix, or the prefix of some of its codes.

    The selector splits before its trailing digits: what precedes them must be a group's prefix in form, and then
    in the index, and the digits, when there are any, one or two that start a rule in service's code. Three digits
    would be a whole code, which the index did not find.

    Args:
        text: The selector, which is neither `ALL` nor any rule's code, name or alias code.
        rule_index: The rule index to read.

    Raises:
        MalformedSelectorError: If it is not a group prefix followed by up to three digits.
        UnknownSelectorError: If no group has the prefix, or no rule in service's code starts with it.
        EngineSelectorError: If the prefix is the engine's group's.
    """
    group_prefix = text.rstrip(digits)
    number_digits = text[len(group_prefix) :]
    if not _is_group_prefix(group_prefix) or len(number_digits) > rule_index.CODE_DIGITS:
        raise MalformedSelectorError(text)
    if len(number_digits) == rule_index.CODE_DIGITS and int(number_digits) == 0:
        raise MalformedSelectorError(text)

    if rule_index.find_group_title(group_prefix) is None:
        raise UnknownSelectorError(text)
    if _is_engine_group(group_prefix, rule_index):
        raise EngineSelectorError(text)
    if not number_digits:
        return GroupSelector(group_prefix)
    if len(number_digits) == rule_index.CODE_DIGITS or not _starts_a_rule_in_service(text, rule_index):
        raise UnknownSelectorError(text)
    return CodePrefixSelector(group_prefix, number_digits)


def _split_code(code: str, rule_index: RuleIndex) -> CodeSelector:
    """Split a code as the index prints it into its group's prefix and its number.

    Args:
        code: A rule's code, such as `OUT006`.
        rule_index: The rule index to read.
    """
    return CodeSelector(code[: -rule_index.CODE_DIGITS], int(code[-rule_index.CODE_DIGITS :]))


def _require_group(registry: Registry, prefix: str) -> RuleGroup:
    """The registry's group with this prefix, which the index held.

    Args:
        registry: Every rule.
        prefix: A group's prefix the index has.

    Raises:
        IndexGroupNotInRegistryError: If the registry has no such group, which the index held.
    """
    group = registry.find_group(prefix)
    if group is None:
        raise IndexGroupNotInRegistryError(prefix)
    return group


def _is_group_prefix(text: str) -> bool:
    """Whether the text has the shape of a group's prefix: uppercase ASCII letters, and not `ALL`.

    Args:
        text: The word of a selector or rule argument to classify.
    """
    return bool(text) and text != _ALL and all(character in ascii_uppercase for character in text)


def _is_engine_group(prefix: str, rule_index: RuleIndex) -> bool:
    """Whether every row of the group with this prefix is an engine condition.

    Args:
        prefix: The prefix of a group the index has.
        rule_index: The rule index to read.
    """
    kinds = {
        kind for code, _name, kind, _level, _aliases in rule_index.RULES if code[: -rule_index.CODE_DIGITS] == prefix
    }
    return kinds == {_CONDITION_KIND}


def _starts_a_rule_in_service(prefix: str, rule_index: RuleIndex) -> bool:
    """Whether the code of some rule in service starts with this text; a removed rule's or a condition's does not count.

    Args:
        prefix: The start of a code, such as `OUT0`.
        rule_index: The rule index to read.
    """
    return any(
        kind == _RULE_KIND and code.startswith(prefix) for code, _name, kind, _level, _aliases in rule_index.RULES
    )


def _has_code_shape(text: str, rule_index: RuleIndex) -> bool:
    """Whether the text has the shape of a rule's code: a group's prefix and three digits, 001 to 999.

    Args:
        text: The word of a selector or rule argument to classify.
        rule_index: The rule index to read.
    """
    group_prefix = text.rstrip(digits)
    number_digits = text[len(group_prefix) :]
    return _is_group_prefix(group_prefix) and len(number_digits) == rule_index.CODE_DIGITS and int(number_digits) != 0


def _has_name_shape(text: str) -> bool:
    """Whether the text has the shape of a rule's name: kebab-case, with no leading, trailing or doubled hyphen.

    Args:
        text: The word of a rule argument to classify.
    """
    if not text or any(character not in _NAME_CHARACTERS for character in text):
        return False
    return not text.startswith('-') and not text.endswith('-') and '--' not in text
