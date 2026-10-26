"""The one-run selection: which rules a run keeps, before the levels decide how each reports.

A selection filters the rule table and nothing else: it never changes a level, so a rule at `allow` stays off
whatever selects it, and it never reaches a rule or the runner. The command line parses `--select` and `--ignore`
into one; no `--select` selects `AllRules`, never an empty set.

Among the selectors of `--select` and `--ignore` that match a rule, the most specific decides and `--ignore` wins a
tie. `ALL` selects every rule; a full rule code selects one.
"""

from dataclasses import dataclass
from typing import assert_never

from .identity import RuleCode


@dataclass(frozen=True, slots=True)
class AllRules:
    """Every rule, the selector `ALL`; a run given no `--select` selects it."""


type RuleSelector = AllRules | RuleCode


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
        # An ignore as specific as the select wins, so `--select LC304 --ignore LC304` keeps no such rule.
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
        case RuleCode():
            return code == selector
        case _:
            assert_never(selector)


def _specificity(selector: RuleSelector) -> int:
    """How specific a selector is: `ALL` ranks 0 and a full rule code ranks 1.

    Args:
        selector: One selector of `--select` or `--ignore`.
    """
    match selector:
        case AllRules():
            return 0
        case RuleCode():
            return 1
        case _:
            assert_never(selector)
