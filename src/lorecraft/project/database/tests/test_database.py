"""The database's declared queries and their recorded reads."""

import ast
from pathlib import Path

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
            QueryRead(PrimitiveRead.HEADINGS, GUIDE),
        }, 'the outer read set includes the inner query and its primitive read'

    def test_read_set_mutations_stay_inside_the_shared_base(self) -> None:
        #: Given
        source_root = Path(__file__).resolve().parents[5] / 'src'

        #: When
        violations = _read_set_mutations(source_root)

        #: Then
        assert violations == (), 'primitive classes expose reads without direct mutation access'
