"""A sample rule at `warn` over the token count: a document holds more than half the tokens a budget allows."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import ClassVar, Protocol, Self

from lorecraft.core.path import RootRelativePath
from lorecraft.project.item import ItemKind
from lorecraft.project.query import (
    CountPrimitives,
    GovernancePrimitives,
    ItemQuery,
    item_structure_specs,
    item_token_count,
)
from lorecraft.project.syntax import FIRST_LINE, TokenCount
from lorecraft.rules.collector import rule
from lorecraft.rules.identity import Level, Release, RuleCode, RuleName
from lorecraft.rules.subject import Gate, MetaSpecPart, QueriedItemRule, WhenMetaSpec

from ..groups import SAMPLE


@dataclass(frozen=True, slots=True)
class BudgetFacts:
    """What the rule reads of a document.

    Attributes:
        count: The tokens in the document's whole file.
        budgets: The structure file and the budget each governing specification sets, where it sets one.
    """

    count: TokenCount
    budgets: tuple[tuple[RootRelativePath, int], ...]


class _GovernanceCountPrimitives(GovernancePrimitives, CountPrimitives, Protocol):
    """The primitives the query reads."""


def _budget_facts(primitives: _GovernanceCountPrimitives) -> BudgetFacts:
    """The document's token count and the budgets that govern it.

    Args:
        primitives: The model state of the document.
    """
    budgets = tuple(
        (spec.path, spec.tokens.value) for spec in primitives.query(item_structure_specs) if spec.tokens is not None
    )
    return BudgetFacts(count=primitives.query(item_token_count), budgets=budgets)


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class OverHalfBudget(QueriedItemRule[BudgetFacts]):
    """A document holds more than half the tokens a budget allows.

    Attributes:
        spec: The structure file that sets the budget.
        token_count: The tokens in the document's whole file.
        budget: The budget, in tokens.
    """

    CODE: ClassVar[RuleCode] = RuleCode(SAMPLE, 1)
    NAME: ClassVar[RuleName] = RuleName('over-half-budget')
    LEVEL: ClassVar[Level] = Level.WARN
    SINCE: ClassVar[Release] = Release('1.0.0')
    APPLIES_TO: ClassVar[Mapping[ItemKind, Gate]] = MappingProxyType(
        {
            ItemKind.DOCUMENT: WhenMetaSpec(MetaSpecPart.BUDGET),
        }
    )

    spec: RootRelativePath
    token_count: int
    budget: int

    def message(self) -> str:
        """Name the tokens found against the budget."""
        return f'over half the budget ({self.token_count} of {self.budget})'

    @classmethod
    def query(cls) -> ItemQuery[BudgetFacts]:
        """The document's token count and the budgets that govern it."""
        return _budget_facts

    @classmethod
    def judge(cls, facts: BudgetFacts, /) -> tuple[Self, ...]:
        """One occurrence for each budget the document holds more than half of.

        Args:
            facts: The document's token count and its budgets.
        """
        token_count = facts.count.value
        return tuple(
            cls(spec=spec, line=FIRST_LINE, token_count=token_count, budget=budget)
            for spec, budget in facts.budgets
            if token_count * 2 > budget
        )
