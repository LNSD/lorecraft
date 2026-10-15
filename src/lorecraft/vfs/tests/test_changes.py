"""The change set between two hand-built snapshots.

Nothing here touches the disk: every snapshot is built with `Snapshot.from_tree`, or from its records where a
symlink a scan would record must be written out by hand.
"""

from collections.abc import Mapping
from pathlib import PurePosixPath

import pytest

from lib.tree import from_tree
from lorecraft.core.mapping import FrozenMapping
from lorecraft.core.num import UnsignedInt
from lorecraft.core.path import RootRelativePath

from ..changes import ChangeKind, ChangeSet, diff
from ..scan_root import ScanRoot
from ..snapshot import (
    DirectoryRecord,
    EntryRecord,
    FileRecord,
    OtherRecord,
    RefusedListing,
    RefusedRead,
    Snapshot,
    SnapshotRecords,
    SymlinkRecord,
)
from ..view import OsRefusal


def _snapshot(records: Mapping[str, EntryRecord], *, scope: tuple[ScanRoot, ...] = ()) -> Snapshot:
    """A snapshot holding `records`, each keyed by its root-relative path as spelled, and `scope`.

    Args:
        records: Each record the snapshot holds, keyed by the path it was recorded at.
        scope: The scan roots the snapshot records it was taken of; none by default, as for one built by hand.
    """
    parsed: dict[RootRelativePath, EntryRecord] = {}
    for raw_path, record in records.items():
        parsed[RootRelativePath.parse(raw_path)] = record
    return Snapshot(SnapshotRecords(parsed), scope=scope)


def _docs_link(name: str, target: str) -> Snapshot:
    """A scan-shaped snapshot whose `docs` directory holds one symlink and nothing else.

    Args:
        name: The symlink's name inside `docs`.
        target: The link's target as a scan would record it, relative to the link's directory.
    """
    return _snapshot(
        {
            '.': DirectoryRecord(listed=True),
            'docs': DirectoryRecord(listed=True),
            f'docs/{name}': SymlinkRecord(PurePosixPath(target)),
        }
    )


def _linked_skill(leads_to: Mapping[str, EntryRecord]) -> Snapshot:
    """A scan-shaped snapshot whose one skill entry links to `skills/review`, plus the records given.

    Args:
        leads_to: What the scan recorded where the link leads; empty when the link dangles.
    """
    return _snapshot(
        {
            '.agents/skills': DirectoryRecord(listed=True),
            '.agents/skills/review': SymlinkRecord(PurePosixPath('../../skills/review')),
            **leads_to,
        }
    )


def _linked_skill_file(data: bytes) -> Snapshot:
    """A scan-shaped snapshot whose `.agents/skills/SKILL.md` links to `REVIEW.md`, read through the link.

    Args:
        data: The bytes recorded for `REVIEW.md`, the file the link leads to.
    """
    return _snapshot(
        {
            '.agents/skills': DirectoryRecord(listed=True),
            '.agents/skills/SKILL.md': SymlinkRecord(PurePosixPath('../../REVIEW.md')),
            'REVIEW.md': FileRecord(data),
        }
    )


@pytest.mark.unit
class TestDiff:
    def test_diff_with_equal_file_snapshots_returns_empty(self) -> None:
        #: Given
        old = from_tree({'docs': {'a.md': b'a'}})
        new = from_tree({'docs': {'a.md': b'a'}})
        expected: ChangeSet = FrozenMapping({})

        #: When
        changes = diff(old, new)

        #: Then
        assert changes == expected, 'two snapshots of the same file and bytes are no change'

    def test_diff_with_the_same_bytes_in_a_new_object_returns_empty(self) -> None:
        #: Given
        old = from_tree({'docs': {'a.md': b'a'}})
        # A distinct bytes object with the same content: a touch, or a save that wrote the same text.
        new = from_tree({'docs': {'a.md': bytes(bytearray(b'a'))}})
        expected: ChangeSet = FrozenMapping({})

        #: When
        changes = diff(old, new)

        #: Then
        assert changes == expected, 'equal bytes are no change, whatever object holds them'

    def test_diff_with_a_symlink_to_the_same_target_returns_empty(self) -> None:
        #: Given
        old = _docs_link('a.md', 'b.md')
        new = _docs_link('a.md', 'b.md')
        expected: ChangeSet = FrozenMapping({})

        #: When
        changes = diff(old, new)

        #: Then
        assert changes == expected, 'a symlink still pointing at the same target is no change'

    def test_diff_with_only_the_scope_changed_returns_empty(self) -> None:
        #: Given
        records = {'docs': DirectoryRecord(listed=True)}
        old = _snapshot(records, scope=(ScanRoot(RootRelativePath.parse('docs'), depth=UnsignedInt(0)),))
        new = _snapshot(records, scope=(ScanRoot(RootRelativePath.parse('docs'), depth=UnsignedInt(1)),))
        expected: ChangeSet = FrozenMapping({})

        #: When
        changes = diff(old, new)

        #: Then
        assert changes == expected, 'a scope is no path, so a change set names no change for it'

    def test_diff_with_only_the_root_listing_changed_returns_empty(self) -> None:
        #: Given
        old = _snapshot({'docs': DirectoryRecord(listed=True)})
        new = _snapshot({'.': DirectoryRecord(listed=True), 'docs': DirectoryRecord(listed=True)})
        expected: ChangeSet = FrozenMapping({})

        #: When
        changes = diff(old, new)

        #: Then
        assert changes == expected, 'the root always exists, so whether a scan listed it is no change'

    def test_diff_with_a_directory_newly_listed_returns_empty(self) -> None:
        #: Given
        old = _snapshot({'docs': DirectoryRecord(listed=True), 'docs/code': DirectoryRecord()})
        new = _snapshot({'docs': DirectoryRecord(listed=True), 'docs/code': DirectoryRecord(listed=True)})
        expected: ChangeSet = FrozenMapping({})

        #: When
        changes = diff(old, new)

        #: Then
        assert changes == expected, "a directory's flags say how the scan reached it, not what is there"

    def test_diff_with_the_same_other_entry_returns_empty(self) -> None:
        #: Given
        old = _snapshot({'docs': DirectoryRecord(listed=True), 'docs/pipe': OtherRecord()})
        new = _snapshot({'docs': DirectoryRecord(listed=True), 'docs/pipe': OtherRecord()})
        expected: ChangeSet = FrozenMapping({})

        #: When
        changes = diff(old, new)

        #: Then
        assert changes == expected, 'an other entry records nothing that could change but its kind'

    def test_diff_with_a_directory_that_can_now_be_listed_returns_it_modified(self) -> None:
        #: Given
        old = _snapshot({'docs': RefusedListing(OsRefusal.PERMISSION_DENIED)})
        new = _snapshot({'docs': DirectoryRecord(listed=True)})

        #: When
        changes = diff(old, new)

        #: Then
        assert changes == {RootRelativePath.parse('docs'): ChangeKind.MODIFIED}, 'a refusal lost is a change'

    def test_diff_with_a_directory_that_can_no_longer_be_listed_returns_it_modified(self) -> None:
        #: Given
        old = _snapshot({'docs': DirectoryRecord(listed=True)})
        new = _snapshot({'docs': RefusedListing(OsRefusal.PERMISSION_DENIED)})

        #: When
        changes = diff(old, new)

        #: Then
        assert changes == {RootRelativePath.parse('docs'): ChangeKind.MODIFIED}, 'a refusal gained is a change'

    def test_diff_with_a_file_that_can_no_longer_be_read_returns_it_modified(self) -> None:
        #: Given
        old = _snapshot({'docs/a.md': FileRecord(b'# A\n')})
        new = _snapshot({'docs/a.md': RefusedRead(OsRefusal.PERMISSION_DENIED)})

        #: When
        changes = diff(old, new)

        #: Then
        assert changes == {RootRelativePath.parse('docs/a.md'): ChangeKind.MODIFIED}, (
            'a file that was read and is now refused is a change'
        )

    def test_diff_with_the_same_refusal_returns_empty(self) -> None:
        #: Given
        old = _snapshot({'docs': RefusedListing(OsRefusal.PERMISSION_DENIED)})
        new = _snapshot({'docs': RefusedListing(OsRefusal.PERMISSION_DENIED, climbed=True)})

        #: When
        changes = diff(old, new)

        #: Then
        assert changes == {}, 'a directory that is refused both times is unchanged, whatever flags it holds'

    def test_diff_with_a_new_file_returns_it_added(self) -> None:
        #: Given
        old = from_tree({'docs': {'a.md': b'a'}})
        new = from_tree({'docs': {'a.md': b'a', 'b.md': b'b'}})
        expected = {RootRelativePath.parse('docs/b.md'): ChangeKind.ADDED}

        #: When
        changes = diff(old, new)

        #: Then
        assert changes == expected, 'a file only the new snapshot holds is reported ADDED, and nothing else'

    def test_diff_with_a_removed_file_returns_it_deleted(self) -> None:
        #: Given
        old = from_tree({'docs': {'a.md': b'a', 'b.md': b'b'}})
        new = from_tree({'docs': {'a.md': b'a'}})
        expected = {RootRelativePath.parse('docs/b.md'): ChangeKind.DELETED}

        #: When
        changes = diff(old, new)

        #: Then
        assert changes == expected, 'a file only the old snapshot holds is reported DELETED, and nothing else'

    def test_diff_with_changed_bytes_returns_the_file_modified(self) -> None:
        #: Given
        old = from_tree({'docs': {'a.md': b'a'}})
        new = from_tree({'docs': {'a.md': b'changed'}})
        expected = {RootRelativePath.parse('docs/a.md'): ChangeKind.MODIFIED}

        #: When
        changes = diff(old, new)

        #: Then
        assert changes == expected, 'a file whose bytes changed is reported MODIFIED'

    def test_diff_with_a_file_replaced_by_a_symlink_returns_it_deleted(self) -> None:
        #: Given
        old = from_tree({'docs': {'a.md': b'a'}})
        new = _docs_link('a.md', 'b.md')
        expected = {RootRelativePath.parse('docs/a.md'): ChangeKind.DELETED}

        #: When
        changes = diff(old, new)

        #: Then
        assert changes == expected, 'a file turned into a symlink is a kind change, reported DELETED'

    def test_diff_with_a_directory_replaced_by_a_symlink_returns_it_and_its_files_deleted(self) -> None:
        #: Given
        old = from_tree({'docs': {'code': {'a.md': b'a'}}})
        new = _docs_link('code', '../elsewhere')
        expected = {
            RootRelativePath.parse('docs/code'): ChangeKind.DELETED,
            RootRelativePath.parse('docs/code/a.md'): ChangeKind.DELETED,
        }

        #: When
        changes = diff(old, new)

        #: Then
        assert changes == expected, 'a directory turned into a symlink is DELETED, and so is every file it held'

    def test_diff_with_a_new_directory_returns_it_and_its_files_added(self) -> None:
        #: Given
        old = from_tree({'docs': {'a.md': b'a'}})
        new = from_tree({'docs': {'a.md': b'a', 'code': {'b.md': b'b', 'c.md': b'c'}}})
        expected = {
            RootRelativePath.parse('docs/code'): ChangeKind.ADDED,
            RootRelativePath.parse('docs/code/b.md'): ChangeKind.ADDED,
            RootRelativePath.parse('docs/code/c.md'): ChangeKind.ADDED,
        }

        #: When
        changes = diff(old, new)

        #: Then
        assert changes == expected, 'a new directory is ADDED, and so is each file inside it'

    def test_diff_with_a_renamed_file_returns_the_old_path_deleted_and_the_new_path_added(self) -> None:
        #: Given
        old = from_tree({'docs': {'a.md': b'same'}})
        new = from_tree({'docs': {'b.md': b'same'}})
        expected = {
            RootRelativePath.parse('docs/a.md'): ChangeKind.DELETED,
            RootRelativePath.parse('docs/b.md'): ChangeKind.ADDED,
        }

        #: When
        changes = diff(old, new)

        #: Then
        assert changes == expected, 'a rename is no special change: the old path is DELETED, the new one ADDED'

    def test_diff_with_a_retargeted_symlink_returns_it_modified(self) -> None:
        #: Given
        old = _docs_link('a.md', 'b.md')
        new = _docs_link('a.md', 'c.md')
        expected = {RootRelativePath.parse('docs/a.md'): ChangeKind.MODIFIED}

        #: When
        changes = diff(old, new)

        #: Then
        assert changes == expected, 'a symlink pointing at a new target is reported MODIFIED'

    def test_diff_with_an_empty_linked_directory_removed_returns_it_deleted(self) -> None:
        #: Given
        # What a following scan records for `.agents/skills/review -> ../../skills/review`: the directory is
        # listed at its resolved path, and no listing of `skills` names it.
        old = _linked_skill({'skills/review': DirectoryRecord(listed=True)})
        new = _linked_skill({})
        expected = {RootRelativePath.parse('skills/review'): ChangeKind.DELETED}

        #: When
        changes = diff(old, new)

        #: Then
        assert changes == expected, 'a listed directory with no listed parent is an entry, so its removal is seen'

    def test_diff_with_an_empty_linked_directory_created_returns_it_added(self) -> None:
        #: Given
        old = _linked_skill({})
        new = _linked_skill({'skills/review': DirectoryRecord(listed=True)})
        expected = {RootRelativePath.parse('skills/review'): ChangeKind.ADDED}

        #: When
        changes = diff(old, new)

        #: Then
        assert changes == expected, 'a directory appearing where the link dangled is reported ADDED'

    def test_diff_with_changed_bytes_behind_a_linked_file_returns_the_resolved_path_modified(self) -> None:
        #: Given
        old = _linked_skill_file(b'old')
        new = _linked_skill_file(b'new')
        expected = {RootRelativePath.parse('REVIEW.md'): ChangeKind.MODIFIED}

        #: When
        changes = diff(old, new)

        #: Then
        assert changes == expected, 'the file a followed link leads to is compared at its resolved path'

    def test_diff_with_a_climbed_directory_removed_returns_it_deleted(self) -> None:
        #: Given
        # What a following scan records for `skills/x -> ../c/tmp/../d`, before and after `c/tmp` is removed: the
        # second walk stops at the missing `c/tmp`, so it climbs out of nothing.
        old = _snapshot(
            {
                'skills': DirectoryRecord(listed=True),
                'skills/x': SymlinkRecord(PurePosixPath('../c/tmp/../d')),
                'c/tmp': DirectoryRecord(climbed=True),
                'c/d': DirectoryRecord(listed=True),
            }
        )
        new = _snapshot(
            {'skills': DirectoryRecord(listed=True), 'skills/x': SymlinkRecord(PurePosixPath('../c/tmp/../d'))}
        )
        expected = {
            RootRelativePath.parse('c/tmp'): ChangeKind.DELETED,
            RootRelativePath.parse('c/d'): ChangeKind.DELETED,
        }

        #: When
        changes = diff(old, new)

        #: Then
        assert changes == expected, 'a directory a chain climbed out of is a record, so a diff sees it go'
