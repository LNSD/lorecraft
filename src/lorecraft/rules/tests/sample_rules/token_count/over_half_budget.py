"""A sample rule at `warn` over the token count: a document holds more than half the tokens a budget allows."""

from dataclasses import dataclass
from typing import ClassVar, Final, Self

from lorecraft.core.path import RootRelativePath
from lorecraft.project.syntax import LineNumber
from lorecraft.rules.declaration import Level, Release, RuleCode, RuleName, rule
from lorecraft.rules.inputs import TokenCountInput, TokenCountRule

from ..groups import SAMPLE

_FIRST_LINE: Final[LineNumber] = LineNumber.parse(1)
"""Where an occurrence is reported: a budget concerns the whole file."""


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class OverHalfBudget(TokenCountRule):
    """A document holds more than half the tokens a budget allows.

    Attributes:
        spec: The structure specification that sets the budget.
        token_count: The tokens in the document's whole file.
        budget: The budget, in tokens.
    """

    CODE: ClassVar[RuleCode] = RuleCode(SAMPLE, 1)
    NAME: ClassVar[RuleName] = RuleName('over-half-budget')
    LEVEL: ClassVar[Level] = Level.WARN
    SINCE: ClassVar[Release] = Release('1.0.0')

    spec: RootRelativePath
    token_count: int
    budget: int

    def message(self) -> str:
        """Name the tokens found against the budget."""
        return f'over half the budget ({self.token_count} of {self.budget})'

    @classmethod
    def check(cls, subject: TokenCountInput) -> tuple[Self, ...]:
        """One occurrence for each budget the document holds more than half of.

        Args:
            subject: The document's token count, with the budgets that govern it.
        """
        return tuple(
            cls(spec=budget.spec, line=_FIRST_LINE, token_count=subject.token_count.value, budget=budget.tokens.value)
            for budget in subject.budgets
            if subject.token_count.value * 2 > budget.tokens.value
        )
