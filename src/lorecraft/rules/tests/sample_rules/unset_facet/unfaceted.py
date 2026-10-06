"""A sample rule over a document that declares no facet, so the runner could never tell when to run it."""

from dataclasses import dataclass
from typing import ClassVar, Self

from lorecraft.project.context import DocumentContext
from lorecraft.rules.declaration import Level, Release, RuleCode, RuleName, rule
from lorecraft.rules.subject import DocumentRule

from ..groups import SAMPLE


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class Unfaceted(DocumentRule):
    """A sample rule that never fires, and leaves `GOVERNED_BY` unbound."""

    CODE: ClassVar[RuleCode] = RuleCode(SAMPLE, 1)
    NAME: ClassVar[RuleName] = RuleName('unfaceted')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('1.0.0')

    def message(self) -> str:
        """Name the condition."""
        return 'never reported'

    @classmethod
    def check(cls, subject: DocumentContext) -> tuple[Self, ...]:
        """No occurrence, whatever the document.

        Args:
            subject: The document judged.
        """
        return ()
