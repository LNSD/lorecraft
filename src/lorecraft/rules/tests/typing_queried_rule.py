"""A queried rule whose query and facts disagree, which the type checker must reject."""

from typing import Self

from lorecraft.project.query import ItemQuery, SymlinkPrimitives, SymlinkQuery
from lorecraft.project.schemas import TitleFacts, title_facts
from lorecraft.rules.subject import QueriedDocumentRule


class WrongQuery(QueriedDocumentRule[int]):
    """Judges an `int` but names a query that returns `TitleFacts`."""

    @classmethod
    def query(cls) -> ItemQuery[TitleFacts]:  # ty: ignore[invalid-method-override]
        """The query, of the wrong type."""
        return title_facts

    @classmethod
    def judge(cls, facts: int, /) -> tuple[Self, ...]:
        """Never judges."""
        return ()


def symlink_query(_: SymlinkPrimitives) -> int:
    """A well-typed symlink query for the subject-kind check below."""
    return 0


class WrongSubjectQuery(QueriedDocumentRule[int]):
    """A document rule naming a symlink query, which the type checker must reject."""

    @classmethod
    def query(cls) -> SymlinkQuery[int]:  # ty: ignore[invalid-method-override]
        """A query for the wrong subject kind."""
        return symlink_query

    @classmethod
    def judge(cls, facts: int, /) -> tuple[Self, ...]:
        """Never judges."""
        return ()
