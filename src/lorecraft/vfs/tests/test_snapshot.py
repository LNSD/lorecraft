"""The snapshot value and the virtual view over hand-built snapshots.

Nothing here touches the disk: every snapshot is built with `Snapshot.from_tree` or from its records, so
the SYMLINK and OTHER entries a scan would record are written out by hand. The scan itself is covered in
`tests/it/test_filesystem.py`.
"""

from collections.abc import Mapping
from pathlib import PurePosixPath
from types import MappingProxyType
from typing import Final, cast

import pytest

from lorecraft.core.mapping import FrozenMapping
from lorecraft.core.path import PathComponent, PathComponentError, RootRelativePath

from ..scan_root import ScanRoot
from ..snapshot import (
    DirectoryRecord,
    EntryRecord,
    FileRecord,
    FileTree,
    OtherRecord,
    Snapshot,
    SymlinkRecord,
    VirtualFileSystem,
)
from ..view import DirEntry, EntryKind, FileSystem, RootExit, TextDecodeError, UnrecordedFileError

ROOT: Final[RootRelativePath] = RootRelativePath.parse('.')


def _snapshot(records: Mapping[str, EntryRecord], *, scope: tuple[ScanRoot, ...] = ()) -> Snapshot:
    """A snapshot holding `records`, each keyed by its root-relative path as spelled, and `scope`.

    Args:
        records: Each record the snapshot holds, keyed by the path it was recorded at.
        scope: The scan roots the snapshot records it was taken of; none by default, as for one built by hand.
    """
    parsed: dict[RootRelativePath, EntryRecord] = {}
    for raw_path, record in records.items():
        parsed[RootRelativePath.parse(raw_path)] = record
    return Snapshot(FrozenMapping(parsed), scope=scope)


def _skills_snapshot() -> Snapshot:
    """A scan-shaped snapshot: a resolved skills directory, a linked agent directory and links inside.

    `.claude/skills` is a scope root that is itself a link, so it is no entry of any listing; `docs/code` has
    an unentered `sub` directory, a link to a file, a dangling link, a looping link, an absolute link, a link
    climbing above the root and a fifo.
    """
    return _snapshot(
        {
            '.agents/skills': DirectoryRecord(listed=True),
            '.agents/skills/alpha': DirectoryRecord(listed=True),
            '.agents/skills/alpha/SKILL.md': FileRecord(b'---\nname: alpha\n---\n'),
            '.agents/skills/beta': SymlinkRecord(PurePosixPath('alpha')),
            '.claude/skills': SymlinkRecord(PurePosixPath('../.agents/skills')),
            'docs': DirectoryRecord(listed=True),
            'docs/code': DirectoryRecord(listed=True),
            'docs/code/a.md': FileRecord(b'# A\n'),
            'docs/code/above': SymlinkRecord(PurePosixPath('../../..')),
            'docs/code/absolute': SymlinkRecord(PurePosixPath('/srv/docs')),
            'docs/code/dangling': SymlinkRecord(PurePosixPath('missing')),
            'docs/code/linked.md': SymlinkRecord(PurePosixPath('a.md')),
            'docs/code/loop': SymlinkRecord(PurePosixPath('loop')),
            'docs/code/pipe': OtherRecord(),
            'docs/code/sub': DirectoryRecord(),
            'docs/code/up': SymlinkRecord(PurePosixPath('../..')),
        }
    )


def _climbing_chain_records() -> dict[str, EntryRecord]:
    """The records of `_climbing_chain_snapshot`, keyed by path as spelled, for a test to change one of."""
    return {
        'a': DirectoryRecord(listed=True),
        'a/b': DirectoryRecord(listed=True),
        'a/b/SKILL.md': FileRecord(b'---\nname: b\n---\n'),
        'a/tmp': DirectoryRecord(listed=True, climbed=True),
        'c/d': DirectoryRecord(listed=True),
        'c/tmp': DirectoryRecord(climbed=True),
        'skills': DirectoryRecord(listed=True, climbed=True),
        'skills/far': SymlinkRecord(PurePosixPath('../c/tmp/../d')),
        'skills/inner': SymlinkRecord(PurePosixPath('../a/tmp')),
        'skills/l': SymlinkRecord(PurePosixPath('../a/tmp/../b')),
        'skills/m': SymlinkRecord(PurePosixPath('../a/b')),
        'skills/nested': SymlinkRecord(PurePosixPath('inner/..')),
    }


# The scope `_climbing_chain_snapshot` was taken of.
CLIMBING_CHAIN_SCOPE: Final[tuple[ScanRoot, ...]] = (
    ScanRoot(RootRelativePath.parse('skills'), depth=1, follow_links=True),
    ScanRoot(RootRelativePath.parse('a'), depth=1),
)


def _climbing_chain_snapshot() -> Snapshot:
    """A scan-shaped snapshot of link chains whose `..` climbs out of a directory stepped into by name.

    The scope is `skills` one level deep through its links, and `a` one level deep. `skills/l` names
    `../a/tmp/../b`, whose `..` climbs out of `a/tmp`, so it leads to `a/b`; `skills/m` names `../a/b`.
    `skills/inner` names `../a/tmp`; `skills/nested` names `inner/..`, whose `..` climbs out of the `a/tmp` that
    `skills/inner` leads to, so it leads to `a`. `skills/far` names `../c/tmp/../d`: the scan lists `c/d`, where
    the link leads, and nothing in `c/tmp`, which only its climbed record shows is a directory. The root `a`
    lists `a`, `a/b` and `a/tmp`. It is what `take_snapshot` records for that tree.
    """
    return _snapshot(_climbing_chain_records(), scope=CLIMBING_CHAIN_SCOPE)


# What a scan records for `.agents/skills/SKILL.md -> ../../REVIEW.md` when it follows the link: the bytes sit at
# the resolved path, in a directory the scan never listed.
FILE_BEHIND_A_LINK: Final[Mapping[str, EntryRecord]] = MappingProxyType(
    {
        '.agents/skills': DirectoryRecord(listed=True),
        '.agents/skills/SKILL.md': SymlinkRecord(PurePosixPath('../../REVIEW.md')),
        'REVIEW.md': FileRecord(b'---\n'),
    }
)


@pytest.mark.unit
class TestSnapshotFromTree:
    def test_from_tree_with_nested_directories_records_every_directory_listed_and_every_file(self) -> None:
        #: Given
        tree: FileTree = {'docs': {'code': {'b.md': b'b', 'a.md': b'a'}, 'glossary.md': b'g'}}

        #: When
        snapshot = Snapshot.from_tree(tree)

        #: Then
        assert snapshot == _snapshot(
            {
                '.': DirectoryRecord(listed=True),
                'docs': DirectoryRecord(listed=True),
                'docs/code': DirectoryRecord(listed=True),
                'docs/code/a.md': FileRecord(b'a'),
                'docs/code/b.md': FileRecord(b'b'),
                'docs/glossary.md': FileRecord(b'g'),
            }
        ), 'every mapping is a listed directory, root included, and every bytes value a file'

    def test_from_tree_with_names_in_another_order_returns_an_equal_snapshot(self) -> None:
        #: Given
        tree: FileTree = {'docs': {'b.md': b'b', 'a.md': b'a'}}

        #: When
        snapshot = Snapshot.from_tree(tree)

        #: Then
        assert snapshot == Snapshot.from_tree({'docs': {'a.md': b'a', 'b.md': b'b'}}), (
            'the order the tree names its entries in is not part of the snapshot'
        )

    def test_from_tree_with_an_empty_tree_lists_the_root_with_no_entries(self) -> None:
        #: Given
        tree: FileTree = {}

        #: When
        snapshot = Snapshot.from_tree(tree)

        #: Then
        assert snapshot == _snapshot({'.': DirectoryRecord(listed=True)}), (
            'the empty tree is the root listed with no entries, no bytes and no link'
        )

    def test_from_tree_with_an_empty_directory_lists_it_with_no_entries(self) -> None:
        #: Given
        tree: FileTree = {'docs': {}}

        #: When
        snapshot = Snapshot.from_tree(tree)

        #: Then
        assert snapshot == _snapshot({'.': DirectoryRecord(listed=True), 'docs': DirectoryRecord(listed=True)}), (
            'an empty mapping is a directory listed with no entries'
        )

    def test_from_tree_with_files_records_an_empty_scope(self) -> None:
        #: Given
        tree: FileTree = {'docs': {'a.md': b'a'}}

        #: When
        snapshot = Snapshot.from_tree(tree)

        #: Then
        assert snapshot.scope == (), 'nothing was scanned, so no scan root is recorded, not even one for docs/'

    def test_from_tree_with_a_name_holding_a_slash_raises_path_component_error(self) -> None:
        #: Given
        tree: FileTree = {'docs/a.md': b'a'}

        #: When
        with pytest.raises(PathComponentError) as exc_info:
            Snapshot.from_tree(tree)

        #: Then
        assert exc_info.value.name == 'docs/a.md', 'a key names one entry, so a nested path is rejected'

    def test_from_tree_with_the_parent_name_raises_path_component_error(self) -> None:
        #: Given
        tree: FileTree = {'docs': {'..': b'a'}}

        #: When
        with pytest.raises(PathComponentError) as exc_info:
            Snapshot.from_tree(tree)

        #: Then
        assert exc_info.value.name == '..', "'..' names no entry of the directory, so it is rejected"


@pytest.mark.unit
class TestSnapshotEquality:
    def test_equal_snapshots_built_twice_compare_equal(self) -> None:
        #: Given
        first = Snapshot.from_tree({'docs': {'a.md': b'a'}})
        second = Snapshot.from_tree({'docs': {'a.md': b'a'}})

        #: When
        equal = first == second

        #: Then
        assert equal, 'two snapshots of the same listings and bytes are equal'

    def test_equal_snapshots_built_twice_hash_equal(self) -> None:
        #: Given
        first = Snapshot.from_tree({'docs': {'a.md': b'a'}})
        second = Snapshot.from_tree({'docs': {'a.md': b'a'}})

        #: When
        distinct = {first, second}

        #: Then
        assert len(distinct) == 1, 'equal snapshots hash equal, so a set holds one'

    def test_snapshots_of_records_taken_in_another_order_compare_equal(self) -> None:
        #: Given
        # `link-10` sorts before `link-2`, so numeric order is not path order
        numeric = _snapshot({f'link-{index}': SymlinkRecord(PurePosixPath('real')) for index in range(12)})
        by_path = _snapshot(
            {f'link-{index}': SymlinkRecord(PurePosixPath('real')) for index in sorted(range(12), key=str)}
        )

        #: When
        equal = numeric == by_path

        #: Then
        assert equal, 'the order the records were taken in is not part of the snapshot'

    def test_snapshots_of_records_taken_in_another_order_hash_equal(self) -> None:
        #: Given
        first = _snapshot({'docs': DirectoryRecord(listed=True), 'docs/a.md': FileRecord(b'a')})
        second = _snapshot({'docs/a.md': FileRecord(b'a'), 'docs': DirectoryRecord(listed=True)})

        #: When
        distinct = {first, second}

        #: Then
        assert len(distinct) == 1, "snapshots equal whatever their records' order hash equal, so a set holds one"

    def test_snapshots_with_different_bytes_compare_unequal(self) -> None:
        #: Given
        before = Snapshot.from_tree({'docs': {'a.md': b'a'}})
        after = Snapshot.from_tree({'docs': {'a.md': b'b'}})

        #: When
        equal = before == after

        #: Then
        assert not equal, 'a change of bytes alone is a different snapshot'

    def test_snapshots_with_different_directory_flags_compare_unequal(self) -> None:
        #: Given
        listed = _snapshot({'docs': DirectoryRecord(listed=True)})
        climbed = _snapshot({'docs': DirectoryRecord(listed=True, climbed=True)})

        #: When
        equal = listed == climbed

        #: Then
        assert not equal, 'how the scan reached a directory is part of what it saw'

    def test_snapshots_with_different_scopes_compare_unequal(self) -> None:
        #: Given
        records = {'docs': DirectoryRecord(listed=True)}
        narrow = _snapshot(records, scope=(ScanRoot(RootRelativePath.parse('docs'), depth=0),))
        wide = _snapshot(records, scope=(ScanRoot(RootRelativePath.parse('docs'), depth=1),))

        #: When
        equal = narrow == wide

        #: Then
        assert not equal, 'a change of scope alone is a different snapshot, since it changes what is in scope'


@pytest.mark.unit
class TestSnapshotSymlinkTargets:
    def test_symlink_targets_of_a_scanned_snapshot_returns_every_link_with_its_target(self) -> None:
        #: Given
        snapshot = _skills_snapshot()

        #: When
        targets = snapshot.symlink_targets()

        #: Then
        assert targets == {
            RootRelativePath.parse('.agents/skills/beta'): PurePosixPath('alpha'),
            RootRelativePath.parse('.claude/skills'): PurePosixPath('../.agents/skills'),
            RootRelativePath.parse('docs/code/above'): PurePosixPath('../../..'),
            RootRelativePath.parse('docs/code/absolute'): PurePosixPath('/srv/docs'),
            RootRelativePath.parse('docs/code/dangling'): PurePosixPath('missing'),
            RootRelativePath.parse('docs/code/linked.md'): PurePosixPath('a.md'),
            RootRelativePath.parse('docs/code/loop'): PurePosixPath('loop'),
            RootRelativePath.parse('docs/code/up'): PurePosixPath('../..'),
        }, 'every symlink record, an entry of a listing or a link met on the way to a scope root, and no other'

    def test_symlink_targets_of_links_recorded_out_of_path_order_returns_them_in_path_order(self) -> None:
        #: Given
        snapshot = _snapshot({'z': SymlinkRecord(PurePosixPath('a')), 'a': SymlinkRecord(PurePosixPath('z'))})

        #: When
        targets = snapshot.symlink_targets()

        #: Then
        assert list(targets) == [RootRelativePath.parse('a'), RootRelativePath.parse('z')], (
            'the links come in path order, whatever order they were recorded in'
        )

    def test_symlink_targets_of_a_snapshot_built_from_a_tree_returns_empty(self) -> None:
        #: Given
        snapshot = Snapshot.from_tree({'docs': {'a.md': b'a'}})

        #: When
        targets = snapshot.symlink_targets()

        #: Then
        assert targets == {}, 'a tree holds directories and files alone'


@pytest.mark.unit
class TestSnapshotClimbedDirectories:
    def test_climbed_directories_of_a_scanned_snapshot_returns_each_directory_climbed_out_of_in_path_order(
        self,
    ) -> None:
        #: Given
        snapshot = _climbing_chain_snapshot()

        #: When
        climbed = snapshot.climbed_directories()

        #: Then
        assert climbed == (
            RootRelativePath.parse('a/tmp'),
            RootRelativePath.parse('c/tmp'),
            RootRelativePath.parse('skills'),
        ), 'every directory record a `..` climbed out of, listed or not'

    def test_climbed_directories_of_a_snapshot_built_from_a_tree_returns_empty(self) -> None:
        #: Given
        snapshot = Snapshot.from_tree({'docs': {'a.md': b'a'}})

        #: When
        climbed = snapshot.climbed_directories()

        #: Then
        assert climbed == (), 'a tree is listed, never climbed out of'


@pytest.mark.unit
class TestFileSystem:
    def test_instantiate_the_abstract_view_raises_type_error(self) -> None:
        #: Given
        # The cast hides which class this is from the type checker, which would otherwise reject the very
        # instantiation under test; at runtime it is still the abstract FileSystem.
        abstract = cast(type[FileSystem], FileSystem)

        #: When
        with pytest.raises(TypeError) as exc_info:
            abstract()

        #: Then
        assert exc_info.type is TypeError, 'the view is abstract: only its implementations instantiate'


@pytest.mark.unit
class TestVirtualFileSystemListDir:
    def test_list_dir_with_a_listed_directory_returns_its_entries_sorted_by_name(self) -> None:
        #: Given
        virtual = VirtualFileSystem(Snapshot.from_tree({'docs': {'b.md': b'', 'a.md': b''}}))

        #: When
        entries = virtual.list_dir(RootRelativePath.parse('docs'))

        #: Then
        assert entries == (
            DirEntry(PathComponent.parse('a.md'), EntryKind.FILE),
            DirEntry(PathComponent.parse('b.md'), EntryKind.FILE),
        ), 'the recorded listing, in name order'

    def test_list_dir_with_a_missing_directory_returns_empty(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/missing')

        #: When
        entries = virtual.list_dir(path)

        #: Then
        assert entries == (), 'docs/missing was never recorded, so it lists as nothing'

    def test_list_dir_with_a_file_returns_empty(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/a.md')

        #: When
        entries = virtual.list_dir(path)

        #: Then
        assert entries == (), 'a file has no listing, so it lists as nothing, like a missing directory'

    def test_list_dir_with_an_unentered_directory_returns_empty(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/sub')

        #: When
        entries = virtual.list_dir(path)

        #: Then
        assert entries == (), 'the scan never entered docs/code/sub, so it lists as nothing'

    def test_list_dir_with_a_symlink_returns_empty(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/linked.md')

        #: When
        entries = virtual.list_dir(path)

        #: Then
        assert entries == (), 'a symlink is never listed through, so it lists as nothing'

    def test_list_dir_with_a_link_to_a_listed_directory_returns_the_directory_entries(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('.claude/skills')

        #: When
        entries = virtual.list_dir(path)

        #: Then
        assert entries == (
            DirEntry(PathComponent.parse('alpha'), EntryKind.DIRECTORY),
            DirEntry(PathComponent.parse('beta'), EntryKind.SYMLINK),
        ), '.claude/skills leads to .agents/skills, which the scan listed, so it lists as that directory'

    def test_list_dir_with_a_link_to_an_unlisted_directory_returns_empty(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/up')

        #: When
        entries = virtual.list_dir(path)

        #: Then
        assert entries == (), 'docs/code/up leads to the root, which the scan never listed, so it lists as nothing'

    def test_list_dir_with_a_path_out_of_scope_returns_empty(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('src')

        #: When
        entries = virtual.list_dir(path)

        #: Then
        assert entries == (), 'src lies outside the scanned scope, so it lists as nothing'

    def test_list_dir_with_a_symlink_entry_lists_it_as_symlink(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        entry = DirEntry(PathComponent.parse('linked.md'), EntryKind.SYMLINK)

        #: When
        entries = virtual.list_dir(RootRelativePath.parse('docs/code'))

        #: Then
        assert entry in entries, 'linked.md is listed as a symlink, never followed to the file it names'

    def test_list_dir_with_an_other_entry_lists_it_as_other(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        entry = DirEntry(PathComponent.parse('pipe'), EntryKind.OTHER)

        #: When
        entries = virtual.list_dir(RootRelativePath.parse('docs/code'))

        #: Then
        assert entry in entries, 'the fifo pipe is listed as other, neither a file nor a directory'

    def test_list_dir_with_the_listed_root_returns_its_entries_without_the_root(self) -> None:
        #: Given
        virtual = VirtualFileSystem(Snapshot.from_tree({'a.md': b'a'}))

        #: When
        entries = virtual.list_dir(ROOT)

        #: Then
        assert entries == (DirEntry(PathComponent.parse('a.md'), EntryKind.FILE),), (
            'the root is its own parent, yet never an entry of its own listing'
        )

    def test_list_dir_with_a_listed_directory_holding_a_climbed_directory_returns_it_once(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_climbing_chain_snapshot())

        #: When
        entries = virtual.list_dir(RootRelativePath.parse('a'))

        #: Then
        assert entries == (
            DirEntry(PathComponent.parse('b'), EntryKind.DIRECTORY),
            DirEntry(PathComponent.parse('tmp'), EntryKind.DIRECTORY),
        ), 'a/tmp is listed and climbed out of, one record, so one entry'

    def test_list_dir_through_a_link_climbing_out_of_a_directory_stepped_into_returns_where_it_leads(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_climbing_chain_snapshot())
        path = RootRelativePath.parse('skills/l')

        #: When
        entries = virtual.list_dir(path)

        #: Then
        assert entries == (DirEntry(PathComponent.parse('SKILL.md'), EntryKind.FILE),), (
            'skills/l leads through a/tmp/.. to a/b'
        )


@pytest.mark.unit
class TestVirtualFileSystemReadText:
    def test_read_text_with_a_utf8_file_returns_its_text(self) -> None:
        #: Given
        virtual = VirtualFileSystem(Snapshot.from_tree({'docs': {'guide.md': '# Guía\n'.encode()}}))

        #: When
        text = virtual.read_text(RootRelativePath.parse('docs/guide.md'))

        #: Then
        assert text == '# Guía\n', 'the recorded bytes are decoded as UTF-8'

    def test_read_text_with_non_utf8_bytes_raises_decode_text_error(self) -> None:
        #: Given
        latin = RootRelativePath.parse('docs/latin.md')
        virtual = VirtualFileSystem(Snapshot.from_tree({'docs': {'latin.md': b'caf\xe9\n'}}))

        #: When
        with pytest.raises(TextDecodeError) as exc_info:
            virtual.read_text(latin)

        #: Then
        assert exc_info.value.path == latin, 'the error names the root-relative file'
        assert isinstance(exc_info.value.source, UnicodeDecodeError), 'the error keeps the decoder failure'

    def test_read_text_with_a_missing_file_raises_read_text_error(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/missing.md')

        #: When
        with pytest.raises(UnrecordedFileError) as exc_info:
            virtual.read_text(path)

        #: Then
        assert type(exc_info.value) is UnrecordedFileError, 'docs/code/missing.md was never recorded, so it is missing'
        assert exc_info.value.path == path, 'the error names the root-relative path that was read'
        assert str(path) in str(exc_info.value), 'the message names the path that was read'

    def test_read_text_with_a_link_to_a_recorded_file_returns_its_text(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/linked.md')

        #: When
        text = virtual.read_text(path)

        #: Then
        assert text == '# A\n', 'linked.md leads to a.md, whose bytes the snapshot recorded, so it reads as that file'

    def test_read_text_with_a_link_to_an_unrecorded_file_raises_read_text_error(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/dangling')

        #: When
        with pytest.raises(UnrecordedFileError) as exc_info:
            virtual.read_text(path)

        #: Then
        assert type(exc_info.value) is UnrecordedFileError, (
            'dangling leads to a path the snapshot holds no bytes for, so it reads as missing'
        )
        assert exc_info.value.path == path, 'the error names the path that was read, not where the link leads'

    def test_read_text_with_a_file_in_no_listing_behind_a_link_returns_its_text(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_snapshot(FILE_BEHIND_A_LINK))
        path = RootRelativePath.parse('.agents/skills/SKILL.md')

        #: When
        text = virtual.read_text(path)

        #: Then
        assert text == '---\n', 'the link leads to REVIEW.md at the root, recorded at its resolved path'

    def test_read_text_with_a_file_behind_a_linked_directory_returns_its_text(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('.claude/skills/alpha/SKILL.md')

        #: When
        text = virtual.read_text(path)

        #: Then
        assert text == '---\nname: alpha\n---\n', (
            '.claude/skills leads to .agents/skills, so the file reads as the one recorded at its resolved path'
        )

    def test_read_text_with_an_other_entry_raises_read_text_error(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/pipe')

        #: When
        with pytest.raises(UnrecordedFileError) as exc_info:
            virtual.read_text(path)

        #: Then
        assert type(exc_info.value) is UnrecordedFileError, (
            'the fifo pipe has no recorded bytes, so it reads as missing'
        )
        assert exc_info.value.path == path, 'the error names the path that was read'

    def test_read_text_with_a_directory_raises_read_text_error(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/sub')

        #: When
        with pytest.raises(UnrecordedFileError) as exc_info:
            virtual.read_text(path)

        #: Then
        assert type(exc_info.value) is UnrecordedFileError, 'a directory has no bytes, so it reads as a missing file'
        assert exc_info.value.path == path, 'the error names the root-relative path that was read'

    def test_read_text_through_a_link_climbing_out_of_a_directory_stepped_into_returns_the_file_text(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_climbing_chain_snapshot())
        path = RootRelativePath.parse('skills/l/SKILL.md')

        #: When
        text = virtual.read_text(path)

        #: Then
        assert text == '---\nname: b\n---\n', 'skills/l leads to a/b, so its SKILL.md reads as a/b/SKILL.md'


@pytest.mark.unit
class TestVirtualFileSystemFindEntryKind:
    def test_find_entry_kind_with_the_root_returns_directory(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())

        #: When
        kind = virtual.find_entry_kind(ROOT)

        #: Then
        assert kind is EntryKind.DIRECTORY, 'the root is a directory, whatever the scan listed'

    def test_find_entry_kind_with_a_listed_file_returns_file(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/a.md')

        #: When
        kind = virtual.find_entry_kind(path)

        #: Then
        assert kind is EntryKind.FILE, 'docs/code lists a.md as a file'

    def test_find_entry_kind_with_an_unentered_directory_returns_directory(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/sub')

        #: When
        kind = virtual.find_entry_kind(path)

        #: Then
        assert kind is EntryKind.DIRECTORY, 'docs/code lists sub as a directory, though the scan never entered it'

    def test_find_entry_kind_with_a_listed_symlink_returns_symlink(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/linked.md')

        #: When
        kind = virtual.find_entry_kind(path)

        #: Then
        assert kind is EntryKind.SYMLINK, 'linked.md is a symlink itself, whatever file it leads to'

    def test_find_entry_kind_with_an_other_entry_returns_other(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/pipe')

        #: When
        kind = virtual.find_entry_kind(path)

        #: Then
        assert kind is EntryKind.OTHER, 'the fifo pipe is neither a file nor a directory'

    def test_find_entry_kind_with_a_linked_scope_root_in_no_listing_returns_symlink(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('.claude/skills')

        #: When
        kind = virtual.find_entry_kind(path)

        #: Then
        assert kind is EntryKind.SYMLINK, '.claude/skills sits in no listing, but the scan recorded it as a link'

    def test_find_entry_kind_with_an_ancestor_of_a_recorded_link_returns_directory(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('.claude')

        #: When
        kind = virtual.find_entry_kind(path)

        #: Then
        assert kind is EntryKind.DIRECTORY, '.claude holds the recorded link .claude/skills, so it is a directory'

    def test_find_entry_kind_behind_a_linked_parent_returns_the_listed_kind(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('.claude/skills/beta')

        #: When
        kind = virtual.find_entry_kind(path)

        #: Then
        assert kind is EntryKind.SYMLINK, (
            '.claude/skills leads to .agents/skills, which lists beta as a link: the link on the way is followed'
        )

    def test_find_entry_kind_with_a_file_in_no_listing_returns_file(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_snapshot(FILE_BEHIND_A_LINK))
        path = RootRelativePath.parse('REVIEW.md')

        #: When
        kind = virtual.find_entry_kind(path)

        #: Then
        assert kind is EntryKind.FILE, 'the root was never listed, but the scan recorded REVIEW.md as a file'

    def test_find_entry_kind_with_a_missing_path_returns_none(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/missing.md')

        #: When
        kind = virtual.find_entry_kind(path)

        #: Then
        assert kind is None, 'docs/code lists no missing.md, so there is nothing there'

    def test_find_entry_kind_behind_a_dangling_link_returns_none(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/dangling/a.md')

        #: When
        kind = virtual.find_entry_kind(path)

        #: Then
        assert kind is None, 'the parent leads nowhere, so nothing is inside it'

    def test_find_entry_kind_with_a_path_out_of_scope_returns_none(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('src')

        #: When
        kind = virtual.find_entry_kind(path)

        #: Then
        assert kind is None, 'src lies outside the scanned scope, so the snapshot holds nothing there'

    def test_find_entry_kind_through_a_link_climbing_out_of_a_directory_stepped_into_returns_the_kind(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_climbing_chain_snapshot())
        path = RootRelativePath.parse('skills/l/SKILL.md')

        #: When
        kind = virtual.find_entry_kind(path)

        #: Then
        assert kind is EntryKind.FILE, 'the parent skills/l leads to a/b, whose listing names SKILL.md a file'


@pytest.mark.unit
class TestVirtualFileSystemFindDir:
    def test_find_dir_with_the_root_returns_the_root(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('.')

        #: When
        resolved = virtual.find_dir(path)

        #: Then
        assert resolved == RootRelativePath.parse('.'), 'the root resolves to itself'

    def test_find_dir_with_a_listed_directory_returns_itself(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code')

        #: When
        resolved = virtual.find_dir(path)

        #: Then
        assert resolved == RootRelativePath.parse('docs/code'), 'a listed directory with no link on its way is itself'

    def test_find_dir_with_an_ancestor_of_a_listing_returns_itself(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('.agents')

        #: When
        resolved = virtual.find_dir(path)

        #: Then
        assert resolved == RootRelativePath.parse('.agents'), (
            '.agents holds the listed .agents/skills, so it is a directory, though never listed itself'
        )

    def test_find_dir_with_an_empty_listing_in_no_listed_parent_returns_itself(self) -> None:
        #: Given
        # an empty scope root: listed, with nothing below it and no listing of its parent to name it
        virtual = VirtualFileSystem(_snapshot({'skills': DirectoryRecord(listed=True)}))
        path = RootRelativePath.parse('skills')

        #: When
        resolved = virtual.find_dir(path)

        #: Then
        assert resolved == RootRelativePath.parse('skills'), 'a listed directory is a directory, even an empty one'

    def test_find_dir_with_an_ancestor_of_a_link_returns_itself(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('.claude')

        #: When
        resolved = virtual.find_dir(path)

        #: Then
        assert resolved == RootRelativePath.parse('.claude'), (
            '.claude holds the recorded link .claude/skills, so it is a directory, though never listed itself'
        )

    def test_find_dir_with_an_unentered_directory_returns_itself(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/sub')

        #: When
        resolved = virtual.find_dir(path)

        #: Then
        assert resolved == RootRelativePath.parse('docs/code/sub'), (
            'docs/code/sub is a directory entry of a listing, so it resolves even though it was never entered'
        )

    def test_find_dir_with_a_relative_link_from_a_subdirectory_returns_the_target(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('.claude/skills')

        #: When
        resolved = virtual.find_dir(path)

        #: Then
        assert resolved == RootRelativePath.parse('.agents/skills'), (
            'the target ../.agents/skills is read from the link directory .claude'
        )

    def test_find_dir_with_a_link_inside_a_listing_returns_the_target(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('.agents/skills/beta')

        #: When
        resolved = virtual.find_dir(path)

        #: Then
        assert resolved == RootRelativePath.parse('.agents/skills/alpha'), (
            'the listed link beta leads to its sibling alpha'
        )

    def test_find_dir_with_a_link_behind_a_linked_parent_returns_the_resolved_directory(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('.claude/skills/beta')

        #: When
        resolved = virtual.find_dir(path)

        #: Then
        assert resolved == RootRelativePath.parse('.agents/skills/alpha'), (
            'the linked parent .claude/skills is followed first, then the link beta inside it'
        )

    def test_find_dir_with_a_link_up_to_the_root_returns_the_root(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/up')

        #: When
        resolved = virtual.find_dir(path)

        #: Then
        assert resolved == RootRelativePath.parse('.'), 'the link up, targeting ../.. from docs/code, leads to the root'

    def test_find_dir_with_a_link_then_listed_components_returns_the_listed_directory(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/up/docs/code')

        #: When
        resolved = virtual.find_dir(path)

        #: Then
        assert resolved == RootRelativePath.parse('docs/code'), (
            'after the link up leads to the root, docs/code is walked through the listings'
        )

    def test_find_dir_with_a_chain_of_40_links_returns_the_directory_it_leads_to(self) -> None:
        #: Given
        # link-0 leads to real and each later link to the one before it, so link-39 heads a chain of 40 links,
        # as many as the kernel follows
        records: dict[str, EntryRecord] = {'real': DirectoryRecord(listed=True)}
        records['link-0'] = SymlinkRecord(PurePosixPath('real'))
        for index in range(1, 40):
            records[f'link-{index}'] = SymlinkRecord(PurePosixPath(f'link-{index - 1}'))
        virtual = VirtualFileSystem(_snapshot(records))
        path = RootRelativePath.parse('link-39')

        #: When
        resolved = virtual.find_dir(path)

        #: Then
        assert resolved == RootRelativePath.parse('real'), 'a chain of 40 links is followed to its end'

    def test_find_dir_with_a_missing_path_returns_none(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/missing')

        #: When
        resolved = virtual.find_dir(path)

        #: Then
        assert resolved is None, 'docs/missing was never recorded, so it leads to no directory'

    def test_find_dir_with_a_file_returns_none(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/a.md')

        #: When
        resolved = virtual.find_dir(path)

        #: Then
        assert resolved is None, 'a file is not a directory'

    def test_find_dir_through_a_file_returns_none(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/a.md/skills')

        #: When
        resolved = virtual.find_dir(path)

        #: Then
        assert resolved is None, 'a path through the file docs/code/a.md leads to no directory'

    def test_find_dir_with_an_other_entry_returns_none(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/pipe')

        #: When
        resolved = virtual.find_dir(path)

        #: Then
        assert resolved is None, 'the fifo pipe is not a directory'

    def test_find_dir_with_a_link_to_a_file_returns_none(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/linked.md')

        #: When
        resolved = virtual.find_dir(path)

        #: Then
        assert resolved is None, 'linked.md leads to the file a.md, which is not a directory'

    def test_find_dir_with_a_dangling_link_returns_none(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/dangling')

        #: When
        resolved = virtual.find_dir(path)

        #: Then
        assert resolved is None, 'dangling targets a path the snapshot never recorded'

    def test_find_dir_with_a_looping_link_returns_none(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/loop')

        #: When
        resolved = virtual.find_dir(path)

        #: Then
        assert resolved is None, 'a link to itself never reaches a directory'

    def test_find_dir_with_an_absolute_link_returns_none(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/absolute')

        #: When
        resolved = virtual.find_dir(path)

        #: Then
        assert resolved is None, 'the absolute target /srv/docs is outside anything the snapshot recorded'

    def test_find_dir_with_a_link_above_the_root_returns_none(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/above')

        #: When
        resolved = virtual.find_dir(path)

        #: Then
        assert resolved is None, 'the target ../../.. climbs above the root, where no directory is root-relative'

    def test_find_dir_inside_an_unentered_directory_returns_none(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/sub/deeper')

        #: When
        resolved = virtual.find_dir(path)

        #: Then
        assert resolved is None, 'the scan never entered docs/code/sub, so nothing inside it is known'

    def test_find_dir_with_a_path_out_of_scope_returns_none(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('src')

        #: When
        resolved = virtual.find_dir(path)

        #: Then
        assert resolved is None, 'src lies outside the scanned scope, so it leads to no directory'

    def test_find_dir_with_a_link_climbing_out_of_a_directory_stepped_into_returns_where_it_leads(
        self,
    ) -> None:
        #: Given
        virtual = VirtualFileSystem(_climbing_chain_snapshot())
        path = RootRelativePath.parse('skills/l')

        #: When
        resolved = virtual.find_dir(path)

        #: Then
        assert resolved == RootRelativePath.parse('a/b'), 'the `..` after a/tmp is its parent, a'

    def test_find_dir_with_a_link_climbing_out_of_a_directory_only_climbed_returns_where_it_leads(
        self,
    ) -> None:
        #: Given
        virtual = VirtualFileSystem(_climbing_chain_snapshot())
        path = RootRelativePath.parse('skills/far')

        #: When
        resolved = virtual.find_dir(path)

        #: Then
        assert resolved == RootRelativePath.parse('c/d'), 'the climbed directories show c/tmp is a directory'

    def test_find_dir_with_a_link_climbing_out_of_an_unrecorded_directory_returns_none(self) -> None:
        #: Given
        records = _climbing_chain_records()
        del records['c/tmp']
        virtual = VirtualFileSystem(_snapshot(records, scope=CLIMBING_CHAIN_SCOPE))
        path = RootRelativePath.parse('skills/far')

        #: When
        resolved = virtual.find_dir(path)

        #: Then
        assert resolved is None, 'without the record nothing shows c/tmp exists, so the walk stops there'

    def test_find_dir_with_a_link_climbing_out_of_its_own_directory_returns_the_target(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_climbing_chain_snapshot())
        path = RootRelativePath.parse('skills/m')

        #: When
        resolved = virtual.find_dir(path)

        #: Then
        assert resolved == RootRelativePath.parse('a/b'), (
            'the target ../a/b climbs only out of skills, where the link sits'
        )

    def test_find_dir_with_a_link_whose_dotdot_climbs_out_of_where_another_link_leads_returns_its_parent(
        self,
    ) -> None:
        #: Given
        virtual = VirtualFileSystem(_climbing_chain_snapshot())
        path = RootRelativePath.parse('skills/nested')

        #: When
        resolved = virtual.find_dir(path)

        #: Then
        assert resolved == RootRelativePath.parse('a'), 'inner/.. climbs out of a/tmp, where skills/inner leads'


@pytest.mark.unit
class TestVirtualFileSystemFindFile:
    def test_find_file_with_a_file_returns_itself(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/a.md')

        #: When
        resolved = virtual.find_file(path)

        #: Then
        assert resolved == RootRelativePath.parse('docs/code/a.md'), 'a recorded file with no link on its way is itself'

    def test_find_file_with_a_link_to_a_file_returns_the_file(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/linked.md')

        #: When
        resolved = virtual.find_file(path)

        #: Then
        assert resolved == RootRelativePath.parse('docs/code/a.md'), 'linked.md leads to its sibling a.md'

    def test_find_file_through_a_linked_parent_and_a_linked_directory_returns_the_resolved_file(
        self,
    ) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('.claude/skills/beta/SKILL.md')

        #: When
        resolved = virtual.find_file(path)

        #: Then
        assert resolved == RootRelativePath.parse('.agents/skills/alpha/SKILL.md'), (
            'the links .claude/skills and beta are followed on the way to the file'
        )

    def test_find_file_with_a_directory_returns_none(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code')

        #: When
        resolved = virtual.find_file(path)

        #: Then
        assert resolved is None, 'a directory is not a file'

    def test_find_file_with_an_other_entry_returns_none(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/pipe')

        #: When
        resolved = virtual.find_file(path)

        #: Then
        assert resolved is None, 'the fifo pipe has no recorded bytes, so it is no regular file'

    def test_find_file_with_a_dangling_link_returns_none(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/dangling')

        #: When
        resolved = virtual.find_file(path)

        #: Then
        assert resolved is None, 'dangling targets a path the snapshot never recorded'

    def test_find_file_with_a_looping_link_returns_none(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/loop')

        #: When
        resolved = virtual.find_file(path)

        #: Then
        assert resolved is None, 'a link to itself never reaches a file'

    def test_find_file_with_an_absolute_link_returns_none(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/absolute')

        #: When
        resolved = virtual.find_file(path)

        #: Then
        assert resolved is None, 'the absolute target /srv/docs is outside anything the snapshot recorded'

    def test_find_file_with_a_missing_path_returns_none(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/missing.md')

        #: When
        resolved = virtual.find_file(path)

        #: Then
        assert resolved is None, 'docs/code/missing.md was never recorded, so it leads to no file'

    def test_find_file_through_a_link_climbing_out_of_a_directory_stepped_into_returns_the_resolved_file(
        self,
    ) -> None:
        #: Given
        virtual = VirtualFileSystem(_climbing_chain_snapshot())
        path = RootRelativePath.parse('skills/l/SKILL.md')

        #: When
        resolved = virtual.find_file(path)

        #: Then
        assert resolved == RootRelativePath.parse('a/b/SKILL.md'), 'skills/l leads through a/tmp/.. to a/b'

    def test_find_file_through_a_link_climbing_out_of_its_own_directory_returns_the_resolved_file(
        self,
    ) -> None:
        #: Given
        virtual = VirtualFileSystem(_climbing_chain_snapshot())
        path = RootRelativePath.parse('skills/m/SKILL.md')

        #: When
        resolved = virtual.find_file(path)

        #: Then
        assert resolved == RootRelativePath.parse('a/b/SKILL.md'), 'the scan follows skills/m to a/b'


@pytest.mark.unit
class TestVirtualFileSystemFindRootExit:
    def test_find_root_exit_with_an_absolute_link_returns_it_and_its_target(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/absolute')

        #: When
        leaves_at = virtual.find_root_exit(path)

        #: Then
        assert leaves_at == RootExit(path, PurePosixPath('/srv/docs')), 'an absolute target is outside the root'

    def test_find_root_exit_with_a_link_climbing_above_the_root_returns_it_and_its_target(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/above')

        #: When
        leaves_at = virtual.find_root_exit(path)

        #: Then
        assert leaves_at == RootExit(path, PurePosixPath('../../..')), 'the third `..` climbs above the root'

    def test_find_root_exit_through_a_link_leading_out_returns_that_link(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/absolute/guide.md')

        #: When
        leaves_at = virtual.find_root_exit(path)

        #: Then
        assert leaves_at == RootExit(RootRelativePath.parse('docs/code/absolute'), PurePosixPath('/srv/docs')), (
            'a path past a link leading out leaves the root at that link'
        )

    def test_find_root_exit_with_a_link_leading_inside_returns_none(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/linked.md')

        #: When
        leaves_at = virtual.find_root_exit(path)

        #: Then
        assert leaves_at is None, 'a link to a file under the root does not leave it'

    def test_find_root_exit_with_a_dangling_link_returns_none(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/dangling')

        #: When
        leaves_at = virtual.find_root_exit(path)

        #: Then
        assert leaves_at is None, 'a link dangling inside the root does not leave it'

    def test_find_root_exit_with_a_looping_link_returns_none(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/loop')

        #: When
        leaves_at = virtual.find_root_exit(path)

        #: Then
        assert leaves_at is None, 'a looping link never reaches outside the root'

    def test_find_root_exit_with_a_regular_file_returns_none(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/a.md')

        #: When
        leaves_at = virtual.find_root_exit(path)

        #: Then
        assert leaves_at is None, 'a path with no link on its way does not leave the root'

    def test_find_root_exit_through_a_link_climbing_out_of_a_directory_stepped_into_returns_none(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_climbing_chain_snapshot())
        path = RootRelativePath.parse('skills/l')

        #: When
        leaves_at = virtual.find_root_exit(path)

        #: Then
        assert leaves_at is None, 'the chain climbs out of a/tmp to a/b, inside the root, so it does not leave it'
