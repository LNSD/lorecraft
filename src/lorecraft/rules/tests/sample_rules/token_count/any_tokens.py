"""A sample rule at `deny` over the token count, which fires on every document a budget governs."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import ClassVar, Self

from lorecraft.core.num import NonZeroUnsignedInt
from lorecraft.project.item import ItemType
from lorecraft.project.query import CountPrimitives, ItemQuery, item_token_count
from lorecraft.project.syntax import LineNumber, TokenCount
from lorecraft.rules.collector import rule
from lorecraft.rules.identity import Level, Release, RuleCode, RuleName
from lorecraft.rules.subject import Gate, QueriedItemRule, SpecPart, WhenSpec

from ..groups import SAMPLE


def _token_count(primitives: CountPrimitives) -> TokenCount:
    """The tokens in the document's whole file.

    Args:
        primitives: The model state of the document.
    """
    return primitives.query(item_token_count)


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class AnyTokens(QueriedItemRule[TokenCount]):
    """A sample rule that fires once on every document a budget governs, whatever its token count.

    Attributes:
        token_count: The tokens in the document's whole file.
    """

    CODE: ClassVar[RuleCode] = RuleCode(SAMPLE, 3)
    NAME: ClassVar[RuleName] = RuleName('any-tokens')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('1.0.0')
    APPLIES_TO: ClassVar[Mapping[ItemType, Gate]] = MappingProxyType(
        {
            ItemType.DOCUMENT: WhenSpec(SpecPart.BUDGET),
        }
    )

    token_count: int

    def message(self) -> str:
        """Name the tokens counted."""
        return f'document counted ({self.token_count} tokens)'

    @classmethod
    def query(cls) -> ItemQuery[TokenCount]:
        """The tokens in the document's whole file."""
        return _token_count

    @classmethod
    def judge(cls, facts: TokenCount, /) -> tuple[Self, ...]:
        """One occurrence at line 1, whatever the count.

        Args:
            facts: The tokens in the document's whole file.
        """
        return (cls(spec=None, line=LineNumber(NonZeroUnsignedInt(1)), token_count=facts.value),)
