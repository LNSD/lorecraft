"""A queried rule whose query and facts disagree, which the type checker must reject."""

from collections.abc import Mapping
from types import MappingProxyType
from typing import ClassVar, Self

from lorecraft.project.item import ItemKind
from lorecraft.project.query import ItemQuery, Query, SymlinkPrimitives
from lorecraft.project.schemas import TitleFacts, title_facts
from lorecraft.rules.subject import BySpec, Facet, Gate, QueriedItemRule


class WrongQuery(QueriedItemRule[int]):
    """Judges an `int` but names a query that returns `TitleFacts`."""

    GATES: ClassVar[Mapping[ItemKind, Gate]] = MappingProxyType(
        {
            ItemKind.DOCUMENT: BySpec(Facet.STRUCTURE),
        }
    )

    @classmethod
    def query(cls) -> ItemQuery[TitleFacts]:  # ty: ignore[invalid-method-override]
        """The query, of the wrong type."""
        return title_facts

    @classmethod
    def judge(cls, facts: int, /) -> tuple[Self, ...]:
        """Never judges."""
        return ()


def symlink_depth(_: SymlinkPrimitives) -> int:
    """A well-typed symlink query for the subject-kind check below."""
    return 0


class WrongSubjectQuery(QueriedItemRule[int]):
    """An item rule naming a symlink query, which the type checker must reject."""

    GATES: ClassVar[Mapping[ItemKind, Gate]] = MappingProxyType(
        {
            ItemKind.DOCUMENT: BySpec(Facet.STRUCTURE),
        }
    )

    @classmethod
    def query(cls) -> Query[SymlinkPrimitives, int]:  # ty: ignore[invalid-method-override]
        """A query for the wrong subject kind."""
        return symlink_depth

    @classmethod
    def judge(cls, facts: int, /) -> tuple[Self, ...]:
        """Never judges."""
        return ()
