"""The one-run selection: which rules a run keeps, before the levels decide how each reports.

A selection filters the rule table and nothing else: it never changes a level, so a rule at `allow` stays off
whatever selects it, and it never reaches a rule or the runner. The command line parses `--select` and `--ignore`
into one; no `--select` selects `AllRules`, never an empty set.

Which of `--select` and `--ignore` decides for a rule follows ruff's rule selection: among the selectors of both that
match the rule, the most specific decides, and `--ignore` wins a tie. From the least specific to the most, a
selector is `ALL`, a group's prefix such as `OUT`, a prefix of a code with one or two of its digits such as `OUT0`,
and a rule's code such as `OUT006`.
"""

from dataclasses import dataclass
from string import digits
from typing import Self, assert_never

from lorecraft.core.error import Error
from lorecraft.rules.declaration import RuleCode, RuleGroup


@dataclass(frozen=True, slots=True)
class AllRules:
    """Every rule, the selector `ALL`; a run given no `--select` selects it."""


class InvalidRuleCodePrefixError(Error):
    """The digits of a code prefix are not one or two ASCII digits, so they start no rule's three-digit number.

    A prefix is a value object parsed from a selector the user typed, so a rejected one is an `Error`, whoever
    constructs it.

    Attributes:
        group: The group the prefix was to start the codes of.
        digits: The rejected digits.
    """

    group: RuleGroup
    digits: str

    def __init__(self, group: RuleGroup, digits: str) -> None:
        self.group = group
        self.digits = digits
        super().__init__(f'code prefix {group.prefix}{digits} must end in one or two digits')


@dataclass(frozen=True, slots=True)
class RuleCodePrefix:
    """The start of some codes of one group: its prefix and the first one or two of a code's three digits.

    It prints as the prefix, then the digits, such as `OUT0` or `LEN00`. A code starts with it when it is in the group
    and its zero-padded number starts with the digits, so `OUT0` matches `OUT006` and not `OUT100`.

    Attributes:
        group: The group whose codes it starts.
        digits: One or two ASCII digits, `0` to `9`; three would be a whole code, and none the group itself.
    """

    group: RuleGroup
    digits: str

    @classmethod
    def parse(cls, group: RuleGroup, digits: str) -> Self:
        """Parse the digits a selector holds after its group's prefix into a prefix of that group's codes.

        Args:
            group: The group whose prefix starts the selector.
            digits: The rest of the selector, as typed.

        Raises:
            InvalidRuleCodePrefixError: If the digits are empty, longer than two, or hold any other character.
        """
        return cls(group, digits)

    def __post_init__(self) -> None:
        """Reject digits that are not one or two ASCII digits.

        Raises:
            InvalidRuleCodePrefixError: If the digits are empty, longer than two, or hold any other character.
        """
        if not 1 <= len(self.digits) <= 2 or any(character not in digits for character in self.digits):
            raise InvalidRuleCodePrefixError(self.group, self.digits)

    def is_prefix_of(self, code: RuleCode) -> bool:
        """Whether a code starts with this prefix.

        Args:
            code: The code of a rule.
        """
        return str(code).startswith(str(self))

    def __str__(self) -> str:
        """The prefix as typed: the group's prefix, then the digits."""
        return f'{self.group.prefix}{self.digits}'


# What one selector names: every rule, a group's rules, the rules whose code starts with a prefix, or one rule.
type RuleSelector = AllRules | RuleGroup | RuleCodePrefix | RuleCode


@dataclass(frozen=True, slots=True)
class RuleSelection:
    """The rules one run keeps: those whose most specific `select` match is more specific than any `ignore` match.

    Attributes:
        select: The selectors selected; `{AllRules()}` when nothing narrows the run. When empty, which the command
            line never builds, it keeps no rule, as an empty `select` does in ruff.
        ignore: The selectors ignored; empty when nothing is.
    """

    select: frozenset[RuleSelector]
    ignore: frozenset[RuleSelector]

    def is_kept(self, code: RuleCode) -> bool:
        """Whether the rule with this code is kept: selected, and not ignored by a selector as specific or more.

        Args:
            code: The code of a rule in service.
        """
        selected = _most_specific_match(self.select, code)
        if selected is None:
            return False
        ignored = _most_specific_match(self.ignore, code)
        if ignored is None:
            return True
        # An ignore as specific as the select wins, so `--select OUT --ignore OUT` keeps no rule of the group.
        return selected > ignored


def _most_specific_match(selectors: frozenset[RuleSelector], code: RuleCode) -> int | None:
    """The specificity of the most specific selector matching a code, or None when none matches it.

    Args:
        selectors: The selectors of one option.
        code: The code of a rule in service.
    """
    matched = [_specificity(selector) for selector in selectors if _is_match(selector, code)]
    if not matched:
        return None
    return max(matched)


def _is_match(selector: RuleSelector, code: RuleCode) -> bool:
    """Whether a selector names the rule with this code.

    Args:
        selector: One selector of `--select` or `--ignore`.
        code: The code of a rule in service.
    """
    match selector:
        case AllRules():
            return True
        case RuleGroup():
            return code.group == selector
        case RuleCodePrefix():
            return selector.is_prefix_of(code)
        case RuleCode():
            return code == selector
        case _:
            assert_never(selector)


def _specificity(selector: RuleSelector) -> int:
    """How specific a selector is, as ruff ranks one: `ALL` 0, a group 1, a code prefix 1 and its digits, a code 4.

    A code prefix ranks by its digits, so `OUT00` is more specific than `OUT0`, and both sit between the group and a
    code, whose three digits rank it above any prefix.

    Args:
        selector: One selector of `--select` or `--ignore`.
    """
    match selector:
        case AllRules():
            return 0
        case RuleGroup():
            return 1
        case RuleCodePrefix():
            return 1 + len(selector.digits)
        case RuleCode():
            return 4
        case _:
            assert_never(selector)
