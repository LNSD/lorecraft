"""The database's declared queries and their recorded reads."""

import pytest

from lib.tree import from_tree
from lorecraft.core.path import RootRelativePath
from lorecraft.project.database import Database, PrimitiveRead, QueryRead
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


def _assign_raw_read(primitives: Primitives) -> None:
    """Try to add the removed mutable read attribute."""
    attribute = 'read'
    setattr(primitives, attribute, set())


def _replace_unrelated_slot(primitives: Primitives) -> None:
    """Try to replace storage through a guessed, un-mangled slot name."""
    slot_name = '_' + 'reads'
    object.__setattr__(primitives, slot_name, set())


def _database() -> Database:
    """Create a database with a readable guide item."""
    return Database.from_snapshot(
        from_tree(
            {
                'docs': {
                    '__meta__': {'code.md': b'# Code\n', 'code.spec.json': b'{}'},
                    'code': {'guide.md': b'# Guide\n'},
                }
            }
        )
    )


@pytest.mark.unit
class TestQueryReads:
    def test_primitive_adapter_rejects_a_raw_read_attribute(self) -> None:
        #: Given
        database = Database.from_snapshot(
            from_tree(
                {'docs': {'__meta__': {'code.md': b'# Code\n', 'code.spec.json': b'{}'}, 'code': {'guide.md': b''}}}
            )
        )

        #: When
        with pytest.raises(AttributeError) as raised:
            database.query(_assign_raw_read, GUIDE)

        #: Then
        assert "has no attribute 'read'" in str(raised.value), 'the slotted adapter has no raw read attribute'

    def test_private_storage_cannot_be_replaced_through_an_unrelated_slot_name(self) -> None:
        #: Given
        database = _database()

        #: When
        with pytest.raises(AttributeError):
            database.query(_replace_unrelated_slot, GUIDE)

        #: Then
        assert database.query_reads(_replace_unrelated_slot, GUIDE) == frozenset(), (
            'an unrelated slot name cannot replace read storage'
        )

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
            QueryRead(PrimitiveRead.HEADINGS, GUIDE),
        }, 'the outer read set includes the inner query and its primitive read'
