"""The database's declared queries and their recorded reads."""

import ast
from dataclasses import replace
from pathlib import Path, PurePosixPath

import pytest

from lib.tree import from_tree
from lorecraft.core.mapping import FrozenMapping
from lorecraft.core.path import RootRelativePath
from lorecraft.project.corpus import CorpusDirectoryRef, CorpusName, ReservedCorpusDirectory
from lorecraft.project.database import Database, PrimitiveRead, QueryRead
from lorecraft.project.item import ItemReadError, MarkdownItemRef, UnlistedItemError
from lorecraft.project.query import CorpusDirectoryPrimitives, Primitives, SymlinkPrimitives
from lorecraft.project.skill import OutsideSymlink, SymlinkRef
from lorecraft.project.syntax import Heading
from lorecraft.vfs import OsRefusal, RefusedRead, RootExit, Snapshot, SnapshotRecords

GUIDE: MarkdownItemRef = MarkdownItemRef(RootRelativePath.parse('docs/code/guide.md'))
TARGET: MarkdownItemRef = MarkdownItemRef(RootRelativePath.parse('docs/feat/target.md'))


_DATABASE_SOURCE = Path('src/lorecraft/project/database/database.py')
_PRIVATE_READ_NAMES = {'_record', '_reads', '__reads', '_ReadSet__reads'}
_REFLECTION_CALLS = {'getattr', 'setattr', 'vars'}


def _enclosing_class(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> ast.ClassDef | None:
    parent = parents.get(node)
    while parent is not None:
        if isinstance(parent, ast.ClassDef):
            return parent
        parent = parents.get(parent)
    return None


def _enclosing_method(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> ast.FunctionDef | None:
    parent = parents.get(node)
    while parent is not None:
        if isinstance(parent, ast.FunctionDef):
            return parent
        parent = parents.get(parent)
    return None


def _read_set_mutations(*roots: Path) -> tuple[tuple[Path, ...], tuple[str, ...]]:
    """Scan Python sources for common read-set bypasses.

    Literal private names in reflection calls are reported, but dynamically built names and deliberate Python
    reflection cannot be closed by this practical in-process guard.
    """
    database_path = next(
        (root / _DATABASE_SOURCE.relative_to('src') for root in roots if root.name == 'src'),
        None,
    )
    files = tuple(sorted((path for root in roots for path in root.rglob('*.py')), key=str))
    violations = []
    for path in files:
        tree = ast.parse(path.read_text())
        parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
        class_definitions = tuple(node for node in tree.body if isinstance(node, ast.ClassDef))
        read_set_root = (
            next((node for node in class_definitions if node.name == '_ReadSet'), None)
            if path == database_path
            else None
        )
        read_set_classes: set[ast.ClassDef] = set()
        bound_classes: dict[str, ast.ClassDef] = {}
        for node in class_definitions:
            if node is read_set_root or any(
                isinstance(base, ast.Name) and bound_classes.get(base.id) in read_set_classes for base in node.bases
            ):
                read_set_classes.add(node)
            bound_classes[node.name] = node

        aliases: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                value = node.value
                targets = node.targets if isinstance(node, ast.Assign) else (node.target,)
                if isinstance(value, ast.Attribute) and value.attr == 'read':
                    aliases.update(target.id for target in targets if isinstance(target, ast.Name))

        for node in ast.walk(tree):
            scope = _enclosing_class(node, parents)
            trusted_read_set_scope = scope in read_set_classes
            if isinstance(node, ast.Attribute) and node.attr in {'_ReadSet__reads', '_reads', '__reads'}:
                method = _enclosing_method(node, parents)
                owns_storage = (
                    scope is read_set_root
                    and method is not None
                    and method.name in {'__init__', '_record', '_recorded_reads'}
                )
                if not owns_storage:
                    violations.append(f'{path.name}:{node.lineno}: private read-set storage access')
            elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else (node.target,)
                if any(isinstance(target, ast.Attribute) and target.attr == 'read' for target in targets):
                    violations.append(f'{path.name}:{node.lineno}: raw read-set assignment')
                elif (
                    isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name) and node.target.id in aliases
                ):
                    violations.append(f'{path.name}:{node.lineno}: aliased read-set mutation')
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in {'add', 'update', 'clear', 'discard', 'remove', 'pop'}
            ):
                receiver = node.func.value
                if isinstance(receiver, ast.Attribute) and receiver.attr == 'read':
                    violations.append(f'{path.name}:{node.lineno}: raw read-set mutation')
                elif isinstance(receiver, ast.Name) and receiver.id in aliases:
                    violations.append(f'{path.name}:{node.lineno}: aliased read-set mutation')
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == '_record':
                if not trusted_read_set_scope:
                    violations.append(f'{path.name}:{node.lineno}: read recording outside its shared base')
            elif isinstance(node, ast.Call):
                function_name = (
                    node.func.id
                    if isinstance(node.func, ast.Name)
                    else (node.func.attr if isinstance(node.func, ast.Attribute) else None)
                )
                if function_name in _REFLECTION_CALLS | {'__setattr__'} and any(
                    isinstance(argument, ast.Constant)
                    and isinstance(argument.value, str)
                    and argument.value in _PRIVATE_READ_NAMES
                    for argument in node.args
                ):
                    violations.append(f'{path.name}:{node.lineno}: reflective read-set access')
    return files, tuple(violations)


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


def _read_set_bypass_examples() -> str:
    """Build source with representative bypass syntax without placing it in the scanned module AST."""
    return '\n'.join(
        (
            'class Adapter:',
            '    def query(self, p):',
            '        p._record(key)',
            '        type(p).__mro__[1]._record(p, key)',
            '        p.read = set()',
            '        p.read.update(keys)',
            '        s = p.read',
            '        s |= {key}',
            "        object.__setattr__(p, '_reads', set())",
            "        setattr(p, '_record', write)",
            "        getattr(p, '_reads')",
            "        vars(p, '_record')",
        )
    )


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
    def test_read_set_is_only_accessed_through_its_shared_base(self) -> None:
        #: Given
        repository_root = Path(__file__).resolve().parents[5]

        #: When
        scanned, violations = _read_set_mutations(repository_root / 'src', repository_root / 'tests')

        #: Then
        assert repository_root / _DATABASE_SOURCE in scanned, 'the guard scans the database implementation'
        assert violations == (), 'primitive queries use the shared read recorder and keep its storage private'

    def test_read_set_guard_finds_representative_bypasses(self, tmp_path: Path) -> None:
        #: Given
        source = _read_set_bypass_examples()
        example = tmp_path / 'bypasses.py'
        example.write_text(source)

        #: When
        scanned, violations = _read_set_mutations(tmp_path)

        #: Then
        assert example in scanned, 'the guard visits the synthetic Python source'
        assert len(violations) >= 8, 'the guard catches direct, aliased, indirect and reflective bypasses'

    def test_read_set_guard_binds_its_exemption_to_the_declared_class(self, tmp_path: Path) -> None:
        #: Given
        database_path = tmp_path / _DATABASE_SOURCE
        database_path.parent.mkdir(parents=True)
        database_path.write_text(
            'class _ReadSet:\n'
            '    def _record(self, key): pass\n'
            '    def _recorded_reads(self): return self.__reads\n'
            'class _ReadSet:\n'
            '    def bypass(self, key):\n'
            '        self._record(key)\n'
            '        return self.__reads\n'
        )

        #: When
        scanned, violations = _read_set_mutations(tmp_path / 'src')

        #: Then
        assert database_path in scanned, 'the fixture uses the exact implementation path'
        assert len(violations) == 2, 'a duplicate class name cannot inherit the holder exemption'

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

    def test_query_memoizes_symlink_subjects_and_records_their_primitive(self) -> None:
        #: Given
        database = Database.from_snapshot(from_tree({}))
        path = RootRelativePath.parse('.agents/skills/outside')
        outside = OutsideSymlink(path, RootExit(path, PurePosixPath('/outside')))
        database._model = replace(database.model(), outside_symlinks=FrozenMapping({path: outside}))
        calls = 0

        def query(primitives: SymlinkPrimitives) -> RootExit:
            nonlocal calls
            calls += 1
            return primitives.leaves_at()

        ref = SymlinkRef(path)

        #: When
        first = database.query(query, ref)
        repeated = database.query(query, ref)

        #: Then
        assert first == outside.leaves_at, 'the query returns the symlink primitive'
        assert repeated == outside.leaves_at, 'the repeated query returns the same fact'
        assert calls == 1, 'the query is memoized on repeated calls'
        assert database.query_reads(query, ref) == {PrimitiveRead.SYMLINK_LEAVES_AT}, 'the primitive read is recorded'

    def test_query_memoizes_corpus_directory_subjects_and_records_their_primitive(self) -> None:
        #: Given
        database = Database.from_snapshot(from_tree({}))
        path = RootRelativePath.parse('docs/skills')
        directory = ReservedCorpusDirectory(path, CorpusName.parse('skills'))
        database._model = replace(database.model(), overlapping_directories=frozenset({directory}))
        calls = 0

        def query(primitives: CorpusDirectoryPrimitives) -> CorpusName:
            nonlocal calls
            calls += 1
            return primitives.reserved_corpus()

        ref = CorpusDirectoryRef(path)

        #: When
        first = database.query(query, ref)
        repeated = database.query(query, ref)

        #: Then
        assert first == directory.corpus, 'the query returns the reserved corpus primitive'
        assert repeated == directory.corpus, 'the repeated query returns the same fact'
        assert calls == 1, 'the query is memoized on repeated calls'
        assert database.query_reads(query, ref) == {PrimitiveRead.RESERVED_CORPUS}, 'the primitive read is recorded'

    def test_query_over_an_unlisted_symlink_raises_unlisted_item_error(self) -> None:
        #: Given
        database = Database.from_snapshot(from_tree({}))
        ref = SymlinkRef(RootRelativePath.parse('.agents/skills/missing'))

        #: When
        with pytest.raises(UnlistedItemError) as raised:
            database.query(lambda primitives: primitives.leaves_at(), ref)

        #: Then
        assert 'no subject' in str(raised.value), 'the unknown symlink is reported as an unlisted subject'

    def test_query_over_an_unlisted_corpus_directory_raises_unlisted_item_error(self) -> None:
        #: Given
        database = Database.from_snapshot(from_tree({}))
        ref = CorpusDirectoryRef(RootRelativePath.parse('docs/skills'))

        #: When
        with pytest.raises(UnlistedItemError) as raised:
            database.query(lambda primitives: primitives.reserved_corpus(), ref)

        #: Then
        assert 'no subject' in str(raised.value), 'the unknown corpus directory is reported as an unlisted subject'
