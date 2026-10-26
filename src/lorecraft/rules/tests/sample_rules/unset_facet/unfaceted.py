"""A sample item rule that leaves its applicability declaration unbound."""

from dataclasses import dataclass
from typing import ClassVar, Self

from lorecraft.project.query import ItemPrimitives, ItemQuery
from lorecraft.rules.collector import rule
from lorecraft.rules.identity import Level, Release, RuleCode, RuleName
from lorecraft.rules.subject import QueriedItemRule

from ..groups import SAMPLE


def _nothing(primitives: ItemPrimitives) -> None:
    """The query of a rule that reads nothing.

    Args:
        primitives: The model state of the document, unread.
    """


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class Unfaceted(QueriedItemRule[None]):
    """A sample rule that never fires and leaves `APPLIES_TO` unbound."""

    CODE: ClassVar[RuleCode] = RuleCode(SAMPLE, 1)
    NAME: ClassVar[RuleName] = RuleName('unfaceted')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('1.0.0')

    def message(self) -> str:
        """Name the condition."""
        return 'never reported'

    @classmethod
    def query(cls) -> ItemQuery[None]:
        """No fact: the rule reads nothing."""
        return _nothing

    @classmethod
    def judge(cls, facts: None, /) -> tuple[Self, ...]:
        """No occurrence, whatever the document.

        Args:
            facts: Nothing.
        """
        return ()
