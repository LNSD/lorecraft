"""A queried rule whose query and facts disagree, which the type checker must reject."""

from typing import Self

from lorecraft.project.query import Primitives, Query, SymlinkPrimitives, SymlinkQuery
from lorecraft.project.schemas import TitleFacts, title_facts
from lorecraft.rules.subject import QueriedDocumentRule


class WrongQuery(QueriedDocumentRule[int]):
    """Judges an `int` but names a query that returns `TitleFacts`."""

    @classmethod
    def query(cls) -> Query[TitleFacts]:  # ty: ignore[invalid-method-override]
        """The query, of the wrong type."""
        return title_facts

    @classmethod
    def judge(cls, facts: int, /) -> tuple[Self, ...]:
        """Never judges."""
        return ()


def symlink_query(_: SymlinkPrimitives) -> int:
    """A well-typed symlink query for the subject-kind check below."""
    return 0


def wrong_subject_query(primitives: Primitives) -> int:
    """The same-subject query contract rejects a query for another subject kind."""
    return primitives.query(symlink_query)  # ty: ignore[invalid-argument-type]


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
