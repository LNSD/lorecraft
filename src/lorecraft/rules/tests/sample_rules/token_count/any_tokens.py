"""A sample rule at `deny` over the token count, which fires on every document a budget governs."""

from dataclasses import dataclass
from typing import ClassVar, Self

from lorecraft.project.context import DocumentContext
from lorecraft.project.syntax import LineNumber
from lorecraft.rules.declaration import Level, Release, RuleCode, RuleName, rule
from lorecraft.rules.subject import DocumentRule, Facet

from ..groups import SAMPLE


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class AnyTokens(DocumentRule):
    """A sample rule that fires once on every document a budget governs, whatever its token count.

    Attributes:
        token_count: The tokens in the document's whole file.
    """

    CODE: ClassVar[RuleCode] = RuleCode(SAMPLE, 3)
    NAME: ClassVar[RuleName] = RuleName('any-tokens')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('1.0.0')
    GOVERNED_BY: ClassVar[Facet] = Facet.BUDGET

    token_count: int

    def message(self) -> str:
        """Name the tokens counted."""
        return f'document counted ({self.token_count} tokens)'

    @classmethod
    def check(cls, subject: DocumentContext) -> tuple[Self, ...]:
        """One occurrence at line 1, whatever the count.

        Args:
            subject: The document, governed by a budget.
        """
        return (cls(spec=None, line=LineNumber.from_int(1), token_count=subject.tokens().value),)
