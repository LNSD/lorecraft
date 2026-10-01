"""The snapshot value and the virtual view over hand-built snapshots.

Nothing here touches the disk: every snapshot is built with ``Snapshot.of_files`` or its constructor, so
the SYMLINK and OTHER entries a scan would record are written out by hand. The scan itself is covered in
``tests/it/test_filesystem.py``.
"""

from pathlib import PurePosixPath
from typing import Final, cast

import pytest

from lorecraft.core.path import RootRelativePath

from ..snapshot import FileBytes, Link, Listing, Snapshot, VirtualFileSystem
from ..view import DirEntry, EntryKind, FileSystem, TextDecodeError, UnrecordedFileError

ROOT: Final[RootRelativePath] = RootRelativePath.parse('.')


def _skills_snapshot() -> Snapshot:
    """A scan-shaped snapshot: a canonical skills directory, a linked agent directory and links inside.

    ``.claude/skills`` is a scope root that is itself a link, so it sits in no listing; ``docs/code`` has an
    unentered ``sub`` directory, a link to a file, a dangling link, a looping link, an absolute link, a link
    climbing above the root and a fifo.
    """
    return Snapshot(
        listings=(
            Listing(
                RootRelativePath.parse('.agents/skills'),
                (DirEntry('alpha', EntryKind.DIRECTORY), DirEntry('beta', EntryKind.SYMLINK)),
            ),
            Listing(RootRelativePath.parse('.agents/skills/alpha'), (DirEntry('SKILL.md', EntryKind.FILE),)),
            Listing(RootRelativePath.parse('docs'), (DirEntry('code', EntryKind.DIRECTORY),)),
            Listing(
                RootRelativePath.parse('docs/code'),
                (
                    DirEntry('a.md', EntryKind.FILE),
                    DirEntry('above', EntryKind.SYMLINK),
                    DirEntry('absolute', EntryKind.SYMLINK),
                    DirEntry('dangling', EntryKind.SYMLINK),
                    DirEntry('linked.md', EntryKind.SYMLINK),
                    DirEntry('loop', EntryKind.SYMLINK),
                    DirEntry('pipe', EntryKind.OTHER),
                    DirEntry('sub', EntryKind.DIRECTORY),
                    DirEntry('up', EntryKind.SYMLINK),
                ),
            ),
        ),
        files=(
            FileBytes(RootRelativePath.parse('.agents/skills/alpha/SKILL.md'), b'---\nname: alpha\n---\n'),
            FileBytes(RootRelativePath.parse('docs/code/a.md'), b'# A\n'),
        ),
        links=(
            Link(RootRelativePath.parse('.agents/skills/beta'), PurePosixPath('alpha')),
            Link(RootRelativePath.parse('.claude/skills'), PurePosixPath('../.agents/skills')),
            Link(RootRelativePath.parse('docs/code/above'), PurePosixPath('../../..')),
            Link(RootRelativePath.parse('docs/code/absolute'), PurePosixPath('/srv/docs')),
            Link(RootRelativePath.parse('docs/code/dangling'), PurePosixPath('missing')),
            Link(RootRelativePath.parse('docs/code/linked.md'), PurePosixPath('a.md')),
            Link(RootRelativePath.parse('docs/code/loop'), PurePosixPath('loop')),
            Link(RootRelativePath.parse('docs/code/up'), PurePosixPath('../..')),
        ),
    )


@pytest.mark.unit
class TestSnapshotOfFiles:
    def test_of_files_with_nested_files_derives_every_listing_and_directory_entry(self) -> None:
        #: Given
        files = {
            RootRelativePath.parse('docs/code/b.md'): b'b',
            RootRelativePath.parse('docs/code/a.md'): b'a',
            RootRelativePath.parse('docs/glossary.md'): b'g',
        }

        #: When
        snapshot = Snapshot.of_files(files)

        #: Then
        assert snapshot.listings == (
            Listing(ROOT, (DirEntry('docs', EntryKind.DIRECTORY),)),
            Listing(
                RootRelativePath.parse('docs'),
                (DirEntry('code', EntryKind.DIRECTORY), DirEntry('glossary.md', EntryKind.FILE)),
            ),
            Listing(
                RootRelativePath.parse('docs/code'),
                (DirEntry('a.md', EntryKind.FILE), DirEntry('b.md', EntryKind.FILE)),
            ),
        ), 'every directory on the way to a file is listed, root included, entries sorted by name'

    def test_of_files_with_unsorted_paths_records_files_sorted_by_path(self) -> None:
        #: Given
        files = {RootRelativePath.parse('docs/b.md'): b'b', RootRelativePath.parse('docs/a.md'): b'a'}

        #: When
        snapshot = Snapshot.of_files(files)

        #: Then
        assert snapshot.files == (
            FileBytes(RootRelativePath.parse('docs/a.md'), b'a'),
            FileBytes(RootRelativePath.parse('docs/b.md'), b'b'),
        ), 'file records are sorted by path whatever the mapping order'

    def test_of_files_with_no_files_returns_an_empty_snapshot(self) -> None:
        #: Given
        files: dict[RootRelativePath, bytes] = {}

        #: When
        snapshot = Snapshot.of_files(files)

        #: Then
        assert snapshot == Snapshot(listings=(), files=(), links=()), 'no files is no listing, no bytes, no link'


@pytest.mark.unit
class TestSnapshotEquality:
    def test_equal_snapshots_built_twice_compare_equal(self) -> None:
        #: Given
        first = Snapshot.of_files({RootRelativePath.parse('docs/a.md'): b'a'})
        second = Snapshot.of_files({RootRelativePath.parse('docs/a.md'): b'a'})

        #: When
        equal = first == second

        #: Then
        assert equal, 'two snapshots of the same listings and bytes are equal'

    def test_equal_snapshots_built_twice_hash_equal(self) -> None:
        #: Given
        first = Snapshot.of_files({RootRelativePath.parse('docs/a.md'): b'a'})
        second = Snapshot.of_files({RootRelativePath.parse('docs/a.md'): b'a'})

        #: When
        distinct = {first, second}

        #: Then
        assert len(distinct) == 1, 'equal snapshots hash equal, so a set holds one'

    def test_snapshots_with_different_bytes_compare_unequal(self) -> None:
        #: Given
        before = Snapshot.of_files({RootRelativePath.parse('docs/a.md'): b'a'})
        after = Snapshot.of_files({RootRelativePath.parse('docs/a.md'): b'b'})

        #: When
        equal = before == after

        #: Then
        assert not equal, 'a change of bytes alone is a different snapshot'


@pytest.mark.unit
class TestSnapshotEntries:
    def test_entries_of_a_scanned_snapshot_returns_every_listed_path_directory_and_scope_root_link(self) -> None:
        #: Given
        snapshot = _skills_snapshot()

        #: When
        entries = snapshot.entries()

        #: Then
        assert entries == {
            RootRelativePath.parse('.agents/skills'): EntryKind.DIRECTORY,
            RootRelativePath.parse('.agents/skills/alpha'): EntryKind.DIRECTORY,
            RootRelativePath.parse('.agents/skills/beta'): EntryKind.SYMLINK,
            RootRelativePath.parse('.agents/skills/alpha/SKILL.md'): EntryKind.FILE,
            RootRelativePath.parse('.claude/skills'): EntryKind.SYMLINK,
            RootRelativePath.parse('docs'): EntryKind.DIRECTORY,
            RootRelativePath.parse('docs/code'): EntryKind.DIRECTORY,
            RootRelativePath.parse('docs/code/a.md'): EntryKind.FILE,
            RootRelativePath.parse('docs/code/above'): EntryKind.SYMLINK,
            RootRelativePath.parse('docs/code/absolute'): EntryKind.SYMLINK,
            RootRelativePath.parse('docs/code/dangling'): EntryKind.SYMLINK,
            RootRelativePath.parse('docs/code/linked.md'): EntryKind.SYMLINK,
            RootRelativePath.parse('docs/code/loop'): EntryKind.SYMLINK,
            RootRelativePath.parse('docs/code/pipe'): EntryKind.OTHER,
            RootRelativePath.parse('docs/code/sub'): EntryKind.DIRECTORY,
            RootRelativePath.parse('docs/code/up'): EntryKind.SYMLINK,
        }, 'every entry of every listing, every listed directory, and the link met on the way to a scope root'

    def test_entries_of_a_snapshot_listing_the_root_leaves_the_root_out(self) -> None:
        #: Given
        snapshot = Snapshot.of_files({RootRelativePath.parse('a.md'): b'a'})

        #: When
        entries = snapshot.entries()

        #: Then
        assert entries == {RootRelativePath.parse('a.md'): EntryKind.FILE}, (
            'the root always exists, so its listing adds no entry of its own'
        )

    def test_entries_of_a_snapshot_with_a_file_in_no_listing_returns_it_as_a_file(self) -> None:
        #: Given
        # What a scan records for `.agents/skills/SKILL.md -> ../../REVIEW.md` when it follows the link: the
        # bytes sit at the real path, in a directory the scan never listed.
        snapshot = Snapshot(
            listings=(Listing(RootRelativePath.parse('.agents/skills'), (DirEntry('SKILL.md', EntryKind.SYMLINK),)),),
            files=(FileBytes(RootRelativePath.parse('REVIEW.md'), b'---\n'),),
            links=(Link(RootRelativePath.parse('.agents/skills/SKILL.md'), PurePosixPath('../../REVIEW.md')),),
        )

        #: When
        entries = snapshot.entries()

        #: Then
        assert entries == {
            RootRelativePath.parse('.agents/skills'): EntryKind.DIRECTORY,
            RootRelativePath.parse('.agents/skills/SKILL.md'): EntryKind.SYMLINK,
            RootRelativePath.parse('REVIEW.md'): EntryKind.FILE,
        }, 'a file a followed link leads to is an entry, though no listing names it'


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
        virtual = VirtualFileSystem(
            Snapshot.of_files({RootRelativePath.parse('docs/b.md'): b'', RootRelativePath.parse('docs/a.md'): b''})
        )

        #: When
        entries = virtual.list_dir(RootRelativePath.parse('docs'))

        #: Then
        assert entries == (
            DirEntry('a.md', EntryKind.FILE),
            DirEntry('b.md', EntryKind.FILE),
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
            DirEntry('alpha', EntryKind.DIRECTORY),
            DirEntry('beta', EntryKind.SYMLINK),
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
        entry = DirEntry('linked.md', EntryKind.SYMLINK)

        #: When
        entries = virtual.list_dir(RootRelativePath.parse('docs/code'))

        #: Then
        assert entry in entries, 'linked.md is listed as a symlink, never followed to the file it names'

    def test_list_dir_with_an_other_entry_lists_it_as_other(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        entry = DirEntry('pipe', EntryKind.OTHER)

        #: When
        entries = virtual.list_dir(RootRelativePath.parse('docs/code'))

        #: Then
        assert entry in entries, 'the fifo pipe is listed as other, neither a file nor a directory'


@pytest.mark.unit
class TestVirtualFileSystemReadText:
    def test_read_text_with_a_utf8_file_returns_its_text(self) -> None:
        #: Given
        virtual = VirtualFileSystem(Snapshot.of_files({RootRelativePath.parse('docs/guide.md'): '# Guía\n'.encode()}))

        #: When
        text = virtual.read_text(RootRelativePath.parse('docs/guide.md'))

        #: Then
        assert text == '# Guía\n', 'the recorded bytes are decoded as UTF-8'

    def test_read_text_with_non_utf8_bytes_raises_decode_text_error(self) -> None:
        #: Given
        latin = RootRelativePath.parse('docs/latin.md')
        virtual = VirtualFileSystem(Snapshot.of_files({latin: b'caf\xe9\n'}))

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
        # What a scan records for `.agents/skills/SKILL.md -> ../../REVIEW.md` when it follows the link.
        snapshot = Snapshot(
            listings=(Listing(RootRelativePath.parse('.agents/skills'), (DirEntry('SKILL.md', EntryKind.SYMLINK),)),),
            files=(FileBytes(RootRelativePath.parse('REVIEW.md'), b'---\n'),),
            links=(Link(RootRelativePath.parse('.agents/skills/SKILL.md'), PurePosixPath('../../REVIEW.md')),),
        )
        virtual = VirtualFileSystem(snapshot)
        path = RootRelativePath.parse('.agents/skills/SKILL.md')

        #: When
        text = virtual.read_text(path)

        #: Then
        assert text == '---\n', 'the link leads to REVIEW.md at the root, recorded at its real path'

    def test_read_text_with_a_file_behind_a_linked_directory_returns_its_text(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('.claude/skills/alpha/SKILL.md')

        #: When
        text = virtual.read_text(path)

        #: Then
        assert text == '---\nname: alpha\n---\n', (
            '.claude/skills leads to .agents/skills, so the file reads as the one recorded at its real path'
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


@pytest.mark.unit
class TestVirtualFileSystemEntryKind:
    def test_entry_kind_with_the_root_returns_directory(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())

        #: When
        kind = virtual.entry_kind(ROOT)

        #: Then
        assert kind is EntryKind.DIRECTORY, 'the root is a directory, whatever the scan listed'

    def test_entry_kind_with_a_listed_file_returns_file(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/a.md')

        #: When
        kind = virtual.entry_kind(path)

        #: Then
        assert kind is EntryKind.FILE, 'docs/code lists a.md as a file'

    def test_entry_kind_with_an_unentered_directory_returns_directory(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/sub')

        #: When
        kind = virtual.entry_kind(path)

        #: Then
        assert kind is EntryKind.DIRECTORY, 'docs/code lists sub as a directory, though the scan never entered it'

    def test_entry_kind_with_a_listed_symlink_returns_symlink(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/linked.md')

        #: When
        kind = virtual.entry_kind(path)

        #: Then
        assert kind is EntryKind.SYMLINK, 'linked.md is a symlink itself, whatever file it leads to'

    def test_entry_kind_with_an_other_entry_returns_other(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/pipe')

        #: When
        kind = virtual.entry_kind(path)

        #: Then
        assert kind is EntryKind.OTHER, 'the fifo pipe is neither a file nor a directory'

    def test_entry_kind_with_a_linked_scope_root_in_no_listing_returns_symlink(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('.claude/skills')

        #: When
        kind = virtual.entry_kind(path)

        #: Then
        assert kind is EntryKind.SYMLINK, '.claude/skills sits in no listing, but the scan recorded it as a link'

    def test_entry_kind_with_an_ancestor_of_a_recorded_link_returns_directory(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('.claude')

        #: When
        kind = virtual.entry_kind(path)

        #: Then
        assert kind is EntryKind.DIRECTORY, '.claude holds the recorded link .claude/skills, so it is a directory'

    def test_entry_kind_behind_a_linked_parent_returns_the_listed_kind(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('.claude/skills/beta')

        #: When
        kind = virtual.entry_kind(path)

        #: Then
        assert kind is EntryKind.SYMLINK, (
            '.claude/skills leads to .agents/skills, which lists beta as a link: the link on the way is followed'
        )

    def test_entry_kind_with_a_file_in_no_listing_returns_file(self) -> None:
        #: Given
        # What a scan records for `.agents/skills/SKILL.md -> ../../REVIEW.md` when it follows the link.
        snapshot = Snapshot(
            listings=(Listing(RootRelativePath.parse('.agents/skills'), (DirEntry('SKILL.md', EntryKind.SYMLINK),)),),
            files=(FileBytes(RootRelativePath.parse('REVIEW.md'), b'---\n'),),
            links=(Link(RootRelativePath.parse('.agents/skills/SKILL.md'), PurePosixPath('../../REVIEW.md')),),
        )
        virtual = VirtualFileSystem(snapshot)
        path = RootRelativePath.parse('REVIEW.md')

        #: When
        kind = virtual.entry_kind(path)

        #: Then
        assert kind is EntryKind.FILE, 'the root was never listed, but the scan recorded REVIEW.md as a file'

    def test_entry_kind_with_a_missing_path_returns_none(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/missing.md')

        #: When
        kind = virtual.entry_kind(path)

        #: Then
        assert kind is None, 'docs/code lists no missing.md, so there is nothing there'

    def test_entry_kind_behind_a_dangling_link_returns_none(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/dangling/a.md')

        #: When
        kind = virtual.entry_kind(path)

        #: Then
        assert kind is None, 'the parent leads nowhere, so nothing is inside it'

    def test_entry_kind_with_a_path_out_of_scope_returns_none(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('src')

        #: When
        kind = virtual.entry_kind(path)

        #: Then
        assert kind is None, 'src lies outside the scanned scope, so the snapshot holds nothing there'


@pytest.mark.unit
class TestVirtualFileSystemResolveDir:
    def test_resolve_dir_with_the_root_returns_the_root(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('.')

        #: When
        resolved = virtual.resolve_dir(path)

        #: Then
        assert resolved == RootRelativePath.parse('.'), 'the root resolves to itself'

    def test_resolve_dir_with_a_listed_directory_returns_itself(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code')

        #: When
        resolved = virtual.resolve_dir(path)

        #: Then
        assert resolved == RootRelativePath.parse('docs/code'), 'a listed directory with no link on its way is itself'

    def test_resolve_dir_with_an_ancestor_of_a_listing_returns_itself(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('.agents')

        #: When
        resolved = virtual.resolve_dir(path)

        #: Then
        assert resolved == RootRelativePath.parse('.agents'), (
            '.agents holds the listed .agents/skills, so it is a directory, though never listed itself'
        )

    def test_resolve_dir_with_an_empty_listing_in_no_listed_parent_returns_itself(self) -> None:
        #: Given
        # an empty scope root: listed, with nothing below it and no listing of its parent to name it
        virtual = VirtualFileSystem(Snapshot(listings=(Listing(RootRelativePath.parse('skills'), ()),), files=()))
        path = RootRelativePath.parse('skills')

        #: When
        resolved = virtual.resolve_dir(path)

        #: Then
        assert resolved == RootRelativePath.parse('skills'), 'a listed directory is a directory, even an empty one'

    def test_resolve_dir_with_an_ancestor_of_a_link_returns_itself(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('.claude')

        #: When
        resolved = virtual.resolve_dir(path)

        #: Then
        assert resolved == RootRelativePath.parse('.claude'), (
            '.claude holds the recorded link .claude/skills, so it is a directory, though never listed itself'
        )

    def test_resolve_dir_with_an_unentered_directory_returns_itself(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/sub')

        #: When
        resolved = virtual.resolve_dir(path)

        #: Then
        assert resolved == RootRelativePath.parse('docs/code/sub'), (
            'docs/code/sub is a directory entry of a listing, so it resolves even though it was never entered'
        )

    def test_resolve_dir_with_a_relative_link_from_a_subdirectory_returns_the_target(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('.claude/skills')

        #: When
        resolved = virtual.resolve_dir(path)

        #: Then
        assert resolved == RootRelativePath.parse('.agents/skills'), (
            'the target ../.agents/skills is read from the link directory .claude'
        )

    def test_resolve_dir_with_a_link_inside_a_listing_returns_the_target(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('.agents/skills/beta')

        #: When
        resolved = virtual.resolve_dir(path)

        #: Then
        assert resolved == RootRelativePath.parse('.agents/skills/alpha'), (
            'the listed link beta leads to its sibling alpha'
        )

    def test_resolve_dir_with_a_link_behind_a_linked_parent_returns_the_real_directory(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('.claude/skills/beta')

        #: When
        resolved = virtual.resolve_dir(path)

        #: Then
        assert resolved == RootRelativePath.parse('.agents/skills/alpha'), (
            'the linked parent .claude/skills is followed first, then the link beta inside it'
        )

    def test_resolve_dir_with_a_link_up_to_the_root_returns_the_root(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/up')

        #: When
        resolved = virtual.resolve_dir(path)

        #: Then
        assert resolved == RootRelativePath.parse('.'), 'the link up, targeting ../.. from docs/code, leads to the root'

    def test_resolve_dir_with_a_link_then_listed_components_returns_the_listed_directory(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/up/docs/code')

        #: When
        resolved = virtual.resolve_dir(path)

        #: Then
        assert resolved == RootRelativePath.parse('docs/code'), (
            'after the link up leads to the root, docs/code is walked through the listings'
        )

    def test_resolve_dir_with_a_chain_of_40_links_returns_the_directory_it_leads_to(self) -> None:
        #: Given
        # link-0 leads to real and each later link to the one before it, so link-39 heads a chain of 40 links,
        # as many as the kernel follows
        chain = [Link(RootRelativePath.parse('link-0'), PurePosixPath('real'))]
        chain += [
            Link(RootRelativePath.parse(f'link-{index}'), PurePosixPath(f'link-{index - 1}')) for index in range(1, 40)
        ]
        snapshot = Snapshot(listings=(Listing(RootRelativePath.parse('real'), ()),), files=(), links=tuple(chain))
        virtual = VirtualFileSystem(snapshot)
        path = RootRelativePath.parse('link-39')

        #: When
        resolved = virtual.resolve_dir(path)

        #: Then
        assert resolved == RootRelativePath.parse('real'), 'a chain of 40 links is followed to its end'

    def test_resolve_dir_with_a_missing_path_returns_none(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/missing')

        #: When
        resolved = virtual.resolve_dir(path)

        #: Then
        assert resolved is None, 'docs/missing was never recorded, so it leads to no directory'

    def test_resolve_dir_with_a_file_returns_none(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/a.md')

        #: When
        resolved = virtual.resolve_dir(path)

        #: Then
        assert resolved is None, 'a file is not a directory'

    def test_resolve_dir_through_a_file_returns_none(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/a.md/skills')

        #: When
        resolved = virtual.resolve_dir(path)

        #: Then
        assert resolved is None, 'a path through the file docs/code/a.md leads to no directory'

    def test_resolve_dir_with_an_other_entry_returns_none(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/pipe')

        #: When
        resolved = virtual.resolve_dir(path)

        #: Then
        assert resolved is None, 'the fifo pipe is not a directory'

    def test_resolve_dir_with_a_link_to_a_file_returns_none(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/linked.md')

        #: When
        resolved = virtual.resolve_dir(path)

        #: Then
        assert resolved is None, 'linked.md leads to the file a.md, which is not a directory'

    def test_resolve_dir_with_a_dangling_link_returns_none(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/dangling')

        #: When
        resolved = virtual.resolve_dir(path)

        #: Then
        assert resolved is None, 'dangling targets a path the snapshot never recorded'

    def test_resolve_dir_with_a_looping_link_returns_none(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/loop')

        #: When
        resolved = virtual.resolve_dir(path)

        #: Then
        assert resolved is None, 'a link to itself never reaches a directory'

    def test_resolve_dir_with_an_absolute_link_returns_none(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/absolute')

        #: When
        resolved = virtual.resolve_dir(path)

        #: Then
        assert resolved is None, 'the absolute target /srv/docs is outside anything the snapshot recorded'

    def test_resolve_dir_with_a_link_above_the_root_returns_none(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/above')

        #: When
        resolved = virtual.resolve_dir(path)

        #: Then
        assert resolved is None, 'the target ../../.. climbs above the root, where no directory is root-relative'

    def test_resolve_dir_inside_an_unentered_directory_returns_none(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/sub/deeper')

        #: When
        resolved = virtual.resolve_dir(path)

        #: Then
        assert resolved is None, 'the scan never entered docs/code/sub, so nothing inside it is known'

    def test_resolve_dir_with_a_path_out_of_scope_returns_none(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('src')

        #: When
        resolved = virtual.resolve_dir(path)

        #: Then
        assert resolved is None, 'src lies outside the scanned scope, so it leads to no directory'


@pytest.mark.unit
class TestVirtualFileSystemResolveFile:
    def test_resolve_file_with_a_file_returns_itself(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/a.md')

        #: When
        resolved = virtual.resolve_file(path)

        #: Then
        assert resolved == RootRelativePath.parse('docs/code/a.md'), 'a recorded file with no link on its way is itself'

    def test_resolve_file_with_a_link_to_a_file_returns_the_file(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/linked.md')

        #: When
        resolved = virtual.resolve_file(path)

        #: Then
        assert resolved == RootRelativePath.parse('docs/code/a.md'), 'linked.md leads to its sibling a.md'

    def test_resolve_file_through_a_linked_parent_and_a_linked_directory_returns_the_real_file(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('.claude/skills/beta/SKILL.md')

        #: When
        resolved = virtual.resolve_file(path)

        #: Then
        assert resolved == RootRelativePath.parse('.agents/skills/alpha/SKILL.md'), (
            'the links .claude/skills and beta are followed on the way to the file'
        )

    def test_resolve_file_with_a_directory_returns_none(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code')

        #: When
        resolved = virtual.resolve_file(path)

        #: Then
        assert resolved is None, 'a directory is not a file'

    def test_resolve_file_with_an_other_entry_returns_none(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/pipe')

        #: When
        resolved = virtual.resolve_file(path)

        #: Then
        assert resolved is None, 'the fifo pipe has no recorded bytes, so it is no regular file'

    def test_resolve_file_with_a_dangling_link_returns_none(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/dangling')

        #: When
        resolved = virtual.resolve_file(path)

        #: Then
        assert resolved is None, 'dangling targets a path the snapshot never recorded'

    def test_resolve_file_with_a_looping_link_returns_none(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/loop')

        #: When
        resolved = virtual.resolve_file(path)

        #: Then
        assert resolved is None, 'a link to itself never reaches a file'

    def test_resolve_file_with_an_absolute_link_returns_none(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/absolute')

        #: When
        resolved = virtual.resolve_file(path)

        #: Then
        assert resolved is None, 'the absolute target /srv/docs is outside anything the snapshot recorded'

    def test_resolve_file_with_a_missing_path_returns_none(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/missing.md')

        #: When
        resolved = virtual.resolve_file(path)

        #: Then
        assert resolved is None, 'docs/code/missing.md was never recorded, so it leads to no file'


@pytest.mark.unit
class TestVirtualFileSystemIsListed:
    def test_is_listed_with_a_listed_directory_returns_true(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code')

        #: When
        listed = virtual.is_listed(path)

        #: Then
        assert listed is True, 'the snapshot holds a listing of docs/code'

    def test_is_listed_with_an_empty_listed_directory_returns_true(self) -> None:
        #: Given
        snapshot = Snapshot(listings=(Listing(RootRelativePath.parse('docs/empty'), ()),), files=())
        virtual = VirtualFileSystem(snapshot)
        path = RootRelativePath.parse('docs/empty')

        #: When
        listed = virtual.is_listed(path)

        #: Then
        assert listed is True, 'a listing with no entries is still a listing: the directory is known to be empty'

    def test_is_listed_through_linked_directories_returns_true_for_the_listed_target(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('.claude/skills/beta')

        #: When
        listed = virtual.is_listed(path)

        #: Then
        assert listed is True, 'the links .claude/skills and beta lead to .agents/skills/alpha, which was listed'

    def test_is_listed_with_an_unentered_directory_returns_false(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/sub')

        #: When
        listed = virtual.is_listed(path)

        #: Then
        assert listed is False, 'sub is an entry of docs/code the scan never entered'

    def test_is_listed_with_an_ancestor_of_a_listing_returns_false(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('.agents')

        #: When
        listed = virtual.is_listed(path)

        #: Then
        assert listed is False, '.agents is known to be a directory, but its entries were never read'

    def test_is_listed_with_a_file_returns_false(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('docs/code/a.md')

        #: When
        listed = virtual.is_listed(path)

        #: Then
        assert listed is False, 'a file leads to no directory'

    def test_is_listed_with_a_path_outside_the_scope_returns_false(self) -> None:
        #: Given
        virtual = VirtualFileSystem(_skills_snapshot())
        path = RootRelativePath.parse('src')

        #: When
        listed = virtual.is_listed(path)

        #: Then
        assert listed is False, 'src lies outside the scanned scope'
