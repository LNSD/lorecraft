"""A queried rule whose query and facts disagree, which the type checker must reject."""

from typing import Self

from lorecraft.project.query import Query
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
