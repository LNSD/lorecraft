"""The change set between two hand-built snapshots.

Nothing here touches the disk: every snapshot is built with ``Snapshot.from_files``, or with its constructor
where a symlink a scan would record must be written out by hand.
"""

from pathlib import PurePosixPath

import pytest

from lorecraft.core.path import RootRelativePath

from ..changes import Change, ChangeKind, ChangeSet, diff
from ..scan_root import ScanRoot
from ..snapshot import FileBytes, Link, Listing, Snapshot
from ..view import DirEntry, EntryKind


def _docs_link(name: str, target: str) -> Snapshot:
    """A scan-shaped snapshot whose `docs` directory holds one symlink and nothing else.

    Args:
        name: The symlink's name inside `docs`.
        target: The link's target as a scan would record it, relative to the link's directory.
    """
    return Snapshot(
        listings=(
            Listing(RootRelativePath.parse('.'), (DirEntry('docs', EntryKind.DIRECTORY),)),
            Listing(RootRelativePath.parse('docs'), (DirEntry(name, EntryKind.SYMLINK),)),
        ),
        files=(),
        links=(Link(RootRelativePath.parse('docs') / name, PurePosixPath(target)),),
    )


def _linked_skill(listings: tuple[Listing, ...]) -> Snapshot:
    """A scan-shaped snapshot whose one skill entry links to `skills/review`, plus the listings given.

    Args:
        listings: What the scan listed where the link leads; empty when the link dangles.
    """
    skills_dir = Listing(RootRelativePath.parse('.agents/skills'), (DirEntry('review', EntryKind.SYMLINK),))
    return Snapshot(
        listings=(skills_dir, *listings),
        files=(),
        links=(Link(RootRelativePath.parse('.agents/skills/review'), PurePosixPath('../../skills/review')),),
    )


def _linked_skill_file(data: bytes) -> Snapshot:
    """A scan-shaped snapshot whose `.agents/skills/SKILL.md` links to `REVIEW.md`, read through the link.

    Args:
        data: The bytes recorded for `REVIEW.md`, the file the link leads to.
    """
    return Snapshot(
        listings=(Listing(RootRelativePath.parse('.agents/skills'), (DirEntry('SKILL.md', EntryKind.SYMLINK),)),),
        files=(FileBytes(RootRelativePath.parse('REVIEW.md'), data),),
        links=(Link(RootRelativePath.parse('.agents/skills/SKILL.md'), PurePosixPath('../../REVIEW.md')),),
    )


@pytest.mark.unit
class TestDiff:
    def test_diff_with_equal_file_snapshots_returns_empty(self) -> None:
        #: Given
        old = Snapshot.from_files({RootRelativePath.parse('docs/a.md'): b'a'})
        new = Snapshot.from_files({RootRelativePath.parse('docs/a.md'): b'a'})
        expected: ChangeSet = frozenset()

        #: When
        changes = diff(old, new)

        #: Then
        assert changes == expected, 'two snapshots of the same file and bytes are no change'

    def test_diff_with_the_same_bytes_in_a_new_object_returns_empty(self) -> None:
        #: Given
        old = Snapshot.from_files({RootRelativePath.parse('docs/a.md'): b'a'})
        # A distinct bytes object with the same content: a touch, or a save that wrote the same text.
        new = Snapshot.from_files({RootRelativePath.parse('docs/a.md'): bytes(bytearray(b'a'))})
        expected: ChangeSet = frozenset()

        #: When
        changes = diff(old, new)

        #: Then
        assert changes == expected, 'equal bytes are no change, whatever object holds them'

    def test_diff_with_a_symlink_to_the_same_target_returns_empty(self) -> None:
        #: Given
        old = _docs_link('a.md', 'b.md')
        new = _docs_link('a.md', 'b.md')
        expected: ChangeSet = frozenset()

        #: When
        changes = diff(old, new)

        #: Then
        assert changes == expected, 'a symlink still pointing at the same target is no change'

    def test_diff_with_only_the_scope_changed_returns_empty(self) -> None:
        #: Given
        listing = Listing(RootRelativePath.parse('docs'), ())
        old = Snapshot(listings=(listing,), files=(), scope=(ScanRoot(RootRelativePath.parse('docs'), depth=0),))
        new = Snapshot(listings=(listing,), files=(), scope=(ScanRoot(RootRelativePath.parse('docs'), depth=1),))
        expected: ChangeSet = frozenset()

        #: When
        changes = diff(old, new)

        #: Then
        assert changes == expected, 'a scope is no path, so a change set names no change for it'

    def test_diff_with_a_new_file_returns_it_added(self) -> None:
        #: Given
        old = Snapshot.from_files({RootRelativePath.parse('docs/a.md'): b'a'})
        new = Snapshot.from_files(
            {RootRelativePath.parse('docs/a.md'): b'a', RootRelativePath.parse('docs/b.md'): b'b'}
        )
        expected = frozenset({Change(RootRelativePath.parse('docs/b.md'), ChangeKind.ADDED)})

        #: When
        changes = diff(old, new)

        #: Then
        assert changes == expected, 'a file only the new snapshot holds is reported ADDED, and nothing else'

    def test_diff_with_a_removed_file_returns_it_deleted(self) -> None:
        #: Given
        old = Snapshot.from_files(
            {RootRelativePath.parse('docs/a.md'): b'a', RootRelativePath.parse('docs/b.md'): b'b'}
        )
        new = Snapshot.from_files({RootRelativePath.parse('docs/a.md'): b'a'})
        expected = frozenset({Change(RootRelativePath.parse('docs/b.md'), ChangeKind.DELETED)})

        #: When
        changes = diff(old, new)

        #: Then
        assert changes == expected, 'a file only the old snapshot holds is reported DELETED, and nothing else'

    def test_diff_with_changed_bytes_returns_the_file_modified(self) -> None:
        #: Given
        old = Snapshot.from_files({RootRelativePath.parse('docs/a.md'): b'a'})
        new = Snapshot.from_files({RootRelativePath.parse('docs/a.md'): b'changed'})
        expected = frozenset({Change(RootRelativePath.parse('docs/a.md'), ChangeKind.MODIFIED)})

        #: When
        changes = diff(old, new)

        #: Then
        assert changes == expected, 'a file whose bytes changed is reported MODIFIED'

    def test_diff_with_a_file_replaced_by_a_symlink_returns_it_deleted(self) -> None:
        #: Given
        old = Snapshot.from_files({RootRelativePath.parse('docs/a.md'): b'a'})
        new = _docs_link('a.md', 'b.md')
        expected = frozenset({Change(RootRelativePath.parse('docs/a.md'), ChangeKind.DELETED)})

        #: When
        changes = diff(old, new)

        #: Then
        assert changes == expected, 'a file turned into a symlink is a kind change, reported DELETED'

    def test_diff_with_a_directory_replaced_by_a_symlink_returns_it_and_its_files_deleted(self) -> None:
        #: Given
        old = Snapshot.from_files({RootRelativePath.parse('docs/code/a.md'): b'a'})
        new = _docs_link('code', '../elsewhere')
        expected = frozenset(
            {
                Change(RootRelativePath.parse('docs/code'), ChangeKind.DELETED),
                Change(RootRelativePath.parse('docs/code/a.md'), ChangeKind.DELETED),
            }
        )

        #: When
        changes = diff(old, new)

        #: Then
        assert changes == expected, 'a directory turned into a symlink is DELETED, and so is every file it held'

    def test_diff_with_a_new_directory_returns_it_and_its_files_added(self) -> None:
        #: Given
        old = Snapshot.from_files({RootRelativePath.parse('docs/a.md'): b'a'})
        new = Snapshot.from_files(
            {
                RootRelativePath.parse('docs/a.md'): b'a',
                RootRelativePath.parse('docs/code/b.md'): b'b',
                RootRelativePath.parse('docs/code/c.md'): b'c',
            }
        )
        expected = frozenset(
            {
                Change(RootRelativePath.parse('docs/code'), ChangeKind.ADDED),
                Change(RootRelativePath.parse('docs/code/b.md'), ChangeKind.ADDED),
                Change(RootRelativePath.parse('docs/code/c.md'), ChangeKind.ADDED),
            }
        )

        #: When
        changes = diff(old, new)

        #: Then
        assert changes == expected, 'a new directory is ADDED, and so is each file inside it'

    def test_diff_with_a_renamed_file_returns_the_old_path_deleted_and_the_new_path_added(self) -> None:
        #: Given
        old = Snapshot.from_files({RootRelativePath.parse('docs/a.md'): b'same'})
        new = Snapshot.from_files({RootRelativePath.parse('docs/b.md'): b'same'})
        expected = frozenset(
            {
                Change(RootRelativePath.parse('docs/a.md'), ChangeKind.DELETED),
                Change(RootRelativePath.parse('docs/b.md'), ChangeKind.ADDED),
            }
        )

        #: When
        changes = diff(old, new)

        #: Then
        assert changes == expected, 'a rename is no special change: the old path is DELETED, the new one ADDED'

    def test_diff_with_a_retargeted_symlink_returns_it_modified(self) -> None:
        #: Given
        old = _docs_link('a.md', 'b.md')
        new = _docs_link('a.md', 'c.md')
        expected = frozenset({Change(RootRelativePath.parse('docs/a.md'), ChangeKind.MODIFIED)})

        #: When
        changes = diff(old, new)

        #: Then
        assert changes == expected, 'a symlink pointing at a new target is reported MODIFIED'

    def test_diff_with_an_empty_linked_directory_removed_returns_it_deleted(self) -> None:
        #: Given
        # What a following scan records for `.agents/skills/review -> ../../skills/review`: the directory is
        # listed at its canonical path, and no listing of `skills` names it.
        old = _linked_skill(listings=(Listing(RootRelativePath.parse('skills/review'), ()),))
        new = _linked_skill(listings=())
        expected = frozenset({Change(RootRelativePath.parse('skills/review'), ChangeKind.DELETED)})

        #: When
        changes = diff(old, new)

        #: Then
        assert changes == expected, 'a listed directory with no listed parent is an entry, so its removal is seen'

    def test_diff_with_an_empty_linked_directory_created_returns_it_added(self) -> None:
        #: Given
        old = _linked_skill(listings=())
        new = _linked_skill(listings=(Listing(RootRelativePath.parse('skills/review'), ()),))
        expected = frozenset({Change(RootRelativePath.parse('skills/review'), ChangeKind.ADDED)})

        #: When
        changes = diff(old, new)

        #: Then
        assert changes == expected, 'a directory appearing where the link dangled is reported ADDED'

    def test_diff_with_changed_bytes_behind_a_linked_file_returns_the_canonical_path_modified(self) -> None:
        #: Given
        old = _linked_skill_file(b'old')
        new = _linked_skill_file(b'new')
        expected = frozenset({Change(RootRelativePath.parse('REVIEW.md'), ChangeKind.MODIFIED)})

        #: When
        changes = diff(old, new)

        #: Then
        assert changes == expected, 'the file a followed link leads to is compared at its canonical path'
