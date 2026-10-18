"""The database's declared queries and their recorded reads."""

import ast
from pathlib import Path

import pytest

from lib.tree import from_tree
from lorecraft.core.path import RootRelativePath
from lorecraft.project.database import Database, PrimitiveRead, QueryRead
from lorecraft.project.item import ItemReadError, MarkdownItemRef
from lorecraft.project.query import Primitives
from lorecraft.project.syntax import Heading
from lorecraft.vfs import OsRefusal, RefusedRead, Snapshot, SnapshotRecords

GUIDE: MarkdownItemRef = MarkdownItemRef(RootRelativePath.parse('docs/code/guide.md'))
TARGET: MarkdownItemRef = MarkdownItemRef(RootRelativePath.parse('docs/feat/target.md'))


def _inner(primitives: Primitives) -> tuple[Heading, ...]:
    """Return the item's headings as a declared query."""
    return primitives.headings()


def _outer(primitives: Primitives) -> tuple[Heading, ...]:
    """Return the inner query's answer as a declared query."""
    return primitives.query(_inner)


def _in_read_set_base(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> bool:
    """Whether an AST node is nested inside the shared read-set base."""
    parent = parents.get(node)
    while parent is not None:
        if isinstance(parent, ast.ClassDef):
            return parent.name == '_ReadSet'
        parent = parents.get(parent)
    return False


def _read_set_mutations(source_root: Path) -> tuple[str, ...]:
    """Find direct read-set mutations outside the shared read-set base."""
    violations = []
    for path in source_root.rglob('*.py'):
        tree = ast.parse(path.read_text())
        parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}

        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr == '_reads' and not _in_read_set_base(node, parents):
                violations.append(f'{path.name}:{node.lineno}: private read set access')
            elif (
                isinstance(node, ast.AugAssign)
                and isinstance(node.target, ast.Attribute)
                and node.target.attr == 'read'
            ):
                violations.append(f'{path.name}:{node.lineno}: augmented read-set mutation')
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == 'add'
                and isinstance(node.func.value, ast.Attribute)
                and node.func.value.attr == 'read'
            ):
                violations.append(f'{path.name}:{node.lineno}: read-set add')
    return tuple(violations)


def _reads_another_item(primitives: Primitives) -> tuple[Heading, ...]:
    """Read headings from another item through the primitive query interface."""
    return primitives.query_at(TARGET, _inner)


def _reads_unreadable_item(primitives: Primitives) -> tuple[Heading, ...]:
    """Read another item while treating an unreadable item as empty."""
    try:
        return primitives.query_at(TARGET, _inner)
    except ItemReadError:
        return ()


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
                        'feat': {'target.md': b'# Target\n'},
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

    def test_read_set_mutations_stay_inside_the_shared_base(self) -> None:
        #: Given
        source_root = Path(__file__).resolve().parents[5] / 'src'

        #: When
        violations = _read_set_mutations(source_root)

        #: Then
        assert violations == (), 'primitive classes expose reads without direct mutation access'

    def test_query_at_records_the_query_and_the_other_item_ref(self) -> None:
        #: Given
        database = Database.from_snapshot(
            from_tree(
                {
                    'docs': {
                        '__meta__': {'code.md': b'# Code\n', 'code.spec.json': b'{}'},
                        'code': {'guide.md': b'# Guide\n'},
                        'feat': {'target.md': b'# Target\n'},
                    }
                }
            )
        )

        #: When
        headings = database.query(_reads_another_item, GUIDE)

        #: Then
        assert tuple(heading.text for heading in headings) == ('Target',), 'the target item query returns its heading'
        assert database.query_reads(_reads_another_item, GUIDE) == {
            QueryRead(_inner, TARGET),
            QueryRead(PrimitiveRead.HEADINGS, TARGET),
        }, 'the read set identifies the query and the primitive it read'

    def test_query_at_records_an_unreadable_other_item(self) -> None:
        #: Given
        snapshot = from_tree(
            {
                'docs': {
                    '__meta__': {'code.md': b'# Code\n', 'code.spec.json': b'{}'},
                    'code': {'guide.md': b'# Guide\n'},
                    'feat': {'target.md': b'# Target\n'},
                }
            }
        )
        records = dict(snapshot.records)
        records[TARGET.path] = RefusedRead(OsRefusal.PERMISSION_DENIED)
        database = Database.from_snapshot(Snapshot(SnapshotRecords(records), scope=snapshot.scope))

        #: When
        headings = database.query(_reads_unreadable_item, GUIDE)

        #: Then
        assert headings == (), 'an unreadable destination contributes no headings'
        assert database.query_reads(_reads_unreadable_item, GUIDE) == {
            QueryRead(_inner, TARGET),
        }, 'the read set retains a failed destination query'
