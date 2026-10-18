"""The database's declared queries and their recorded reads."""

import pytest

from lib.tree import from_tree
from lorecraft.core.path import RootRelativePath
from lorecraft.project.database import Database, QueryRead
from lorecraft.project.item import MarkdownItemRef
from lorecraft.project.query import Primitives
from lorecraft.project.syntax import Heading

GUIDE: MarkdownItemRef = MarkdownItemRef(RootRelativePath.parse('docs/code/guide.md'))


def _inner(primitives: Primitives) -> tuple[Heading, ...]:
    """Return the item's headings as a declared query."""
    return primitives.headings()


def _outer(primitives: Primitives) -> tuple[Heading, ...]:
    """Return the inner query's answer as a declared query."""
    return primitives.query(_inner)


@pytest.mark.unit
class TestQueryReads:
    def test_query_reads_with_a_composed_query_includes_inner_query_and_primitive(self) -> None:
        #: Given
        database = Database.from_snapshot(
            from_tree(
                {
                    'docs': {
                        '__meta__': {'code.md': b'# Code\n', 'code.spec.json': b'{}'},
                        'code': {'guide.md': b'# Guide\n'},
                    }
                }
            )
        )

        #: When
        database.query(_outer, GUIDE)

        #: Then
        assert database.query_reads(_outer, GUIDE) == {
            QueryRead(_inner, GUIDE),
            QueryRead('headings', GUIDE),
        }, 'the outer read set includes the inner query and its primitive read'
