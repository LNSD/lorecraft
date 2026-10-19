"""A sample rule at `allow` over the token count: a document holds no token at all."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import ClassVar, Self

from lorecraft.core.num import NonZeroUnsignedInt
from lorecraft.project.item import ItemKind
from lorecraft.project.query import CountPrimitives, ItemQuery, item_token_count
from lorecraft.project.syntax import LineNumber, TokenCount
from lorecraft.rules.collector import rule
from lorecraft.rules.identity import Level, Release, RuleCode, RuleName
from lorecraft.rules.subject import ByMetaSpec, Gate, MetaSpecPart, QueriedItemRule

from ..groups import SAMPLE


def _token_count(primitives: CountPrimitives) -> TokenCount:
    """The tokens in the document's whole file.

    Args:
        primitives: The model state of the document.
    """
    return primitives.query(item_token_count)


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class EmptyDocument(QueriedItemRule[TokenCount]):
    """A document holds no token at all."""

    CODE: ClassVar[RuleCode] = RuleCode(SAMPLE, 2)
    NAME: ClassVar[RuleName] = RuleName('empty-document')
    LEVEL: ClassVar[Level] = Level.ALLOW
    SINCE: ClassVar[Release] = Release('1.0.0')
    GATES: ClassVar[Mapping[ItemKind, Gate]] = MappingProxyType(
        {
            ItemKind.DOCUMENT: ByMetaSpec(MetaSpecPart.BUDGET),
        }
    )

    def message(self) -> str:
        """Name the condition."""
        return 'document is empty'

    @classmethod
    def query(cls) -> ItemQuery[TokenCount]:
        """The tokens in the document's whole file."""
        return _token_count

    @classmethod
    def judge(cls, facts: TokenCount, /) -> tuple[Self, ...]:
        """The occurrence at line 1, when the document has no token.

        Args:
            facts: The tokens in the document's whole file.
        """
        if facts.value > 0:
            return ()
        return (cls(spec=None, line=LineNumber(NonZeroUnsignedInt(1))),)
