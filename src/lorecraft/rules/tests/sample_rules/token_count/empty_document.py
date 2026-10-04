"""A sample rule at `allow` over the token count: a document holds no token at all."""

from dataclasses import dataclass
from typing import ClassVar, Self

from lorecraft.project.syntax import LineNumber
from lorecraft.rules.declaration import Level, Release, RuleCode, RuleName, rule
from lorecraft.rules.inputs import TokenCountInput, TokenCountRule

from ..groups import SAMPLE


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class EmptyDocument(TokenCountRule):
    """A document holds no token at all."""

    CODE: ClassVar[RuleCode] = RuleCode(SAMPLE, 2)
    NAME: ClassVar[RuleName] = RuleName('empty-document')
    LEVEL: ClassVar[Level] = Level.ALLOW
    SINCE: ClassVar[Release] = Release('1.0.0')

    def message(self) -> str:
        """Name the condition."""
        return 'document is empty'

    @classmethod
    def check(cls, subject: TokenCountInput) -> tuple[Self, ...]:
        """The occurrence at line 1, when the document has no token.

        Args:
            subject: The document's token count, with the budgets that govern it.
        """
        if subject.token_count.value > 0:
            return ()
        return (cls(spec=None, line=LineNumber.parse(1)),)
