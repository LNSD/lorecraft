"""The one join from a root-relative path onto a disk root, and how a scan merges what it records.

The scan itself reads the disk and is covered in `tests/it/test_filesystem.py`; its recorder is pure, so how it
merges a path found twice, and how it refuses one found as two kinds, is covered here without a tree changing
under a scan. No test drives `take_snapshot` to raise `ChangedSnapshotEntryError`: only a tree changing mid-scan
does, and staging one would patch a module internal to steer the scan, which tests-organization.md rules out.
"""

from pathlib import Path, PurePosixPath

import pytest

from lorecraft.core.mapping import FrozenMapping
from lorecraft.core.path import RootRelativePath

from ..disk import ChangedSnapshotEntryError, _SnapshotRecorder, disk_location
from ..snapshot import DirectoryRecord, FileRecord, SymlinkRecord
from ..view import EntryKind


def _path(raw: str) -> RootRelativePath:
    """Parse a root-relative path written in a test.

    Args:
        raw: The path with `/` separators.
    """
    return RootRelativePath.parse(raw)


@pytest.mark.unit
class TestDiskLocation:
    def test_disk_location_of_a_path_returns_the_location_below_the_root(self, tmp_path: Path) -> None:
        #: Given
        path = RootRelativePath.parse('docs/code/a.md')

        #: When
        location = disk_location(tmp_path, path)

        #: Then
        assert location == tmp_path / 'docs' / 'code' / 'a.md', 'the path is joined onto the root, never replacing it'

    def test_disk_location_of_the_root_returns_the_disk_root(self, tmp_path: Path) -> None:
        #: Given
        root = RootRelativePath.parse('.')

        #: When
        location = disk_location(tmp_path, root)

        #: Then
        assert location == tmp_path, 'the root-relative root is the disk root itself'


@pytest.mark.unit
class TestSnapshotRecorder:
    def test_record_with_a_path_recorded_nowhere_records_what_was_found(self) -> None:
        #: Given
        recorder = _SnapshotRecorder()

        #: When
        recorder.record(_path('docs/a.md'), FileRecord(b'a'))

        #: Then
        assert recorder.to_records() == FrozenMapping({_path('docs/a.md'): FileRecord(b'a')}), (
            'the first record of a path is kept as found'
        )

    def test_record_with_a_climb_out_of_a_listed_directory_merges_both_flags(self) -> None:
        #: Given
        recorder = _SnapshotRecorder()
        recorder.record(_path('skills/tmp'), DirectoryRecord(listed=True))

        #: When
        recorder.record(_path('skills/tmp'), DirectoryRecord(climbed=True))

        #: Then
        assert recorder.to_records() == FrozenMapping(
            {_path('skills/tmp'): DirectoryRecord(listed=True, climbed=True)}
        ), 'each directory record says one way the scan reached it, so the merge keeps both'

    def test_record_with_a_directory_entry_after_its_listing_keeps_it_listed(self) -> None:
        #: Given
        # a scope root listed first, then named again by the listing of its parent
        recorder = _SnapshotRecorder()
        recorder.record(_path('docs'), DirectoryRecord(listed=True))

        #: When
        recorder.record(_path('docs'), DirectoryRecord())

        #: Then
        assert recorder.to_records() == FrozenMapping({_path('docs'): DirectoryRecord(listed=True)}), (
            'a flag once set stays set, whatever order the scan reaches the directory in'
        )

    def test_record_with_a_file_read_again_with_other_bytes_keeps_the_last_read(self) -> None:
        #: Given
        recorder = _SnapshotRecorder()
        recorder.record(_path('docs/a.md'), FileRecord(b'first'))

        #: When
        recorder.record(_path('docs/a.md'), FileRecord(b'second'))

        #: Then
        assert recorder.to_records() == FrozenMapping({_path('docs/a.md'): FileRecord(b'second')}), (
            'a file that changed between two reads keeps its last bytes, and the scan goes on'
        )

    def test_record_with_a_link_read_again_with_another_target_keeps_the_last_read(self) -> None:
        #: Given
        recorder = _SnapshotRecorder()
        recorder.record(_path('skills/x'), SymlinkRecord(PurePosixPath('a')))

        #: When
        recorder.record(_path('skills/x'), SymlinkRecord(PurePosixPath('b')))

        #: Then
        assert recorder.to_records() == FrozenMapping({_path('skills/x'): SymlinkRecord(PurePosixPath('b'))}), (
            'a link retargeted between two reads keeps its last target, and the scan goes on'
        )

    def test_record_with_a_symlink_where_a_directory_was_recorded_raises_changed_snapshot_entry_error(self) -> None:
        #: Given
        # a directory listed as an entry of its parent, then replaced by a symlink before a walk steps through it
        recorder = _SnapshotRecorder()
        recorder.record(_path('docs/code'), DirectoryRecord())

        #: When
        with pytest.raises(ChangedSnapshotEntryError) as exc_info:
            recorder.record(_path('docs/code'), SymlinkRecord(PurePosixPath('elsewhere')))

        #: Then
        assert exc_info.value.path == _path('docs/code'), 'the error names the path found as two kinds'
        assert exc_info.value.recorded is EntryKind.DIRECTORY, 'the kind recorded first is the directory'
        assert exc_info.value.found is EntryKind.SYMLINK, 'the kind found later is the symlink'

    def test_record_below_a_path_recorded_as_a_file_raises_changed_snapshot_entry_error(self) -> None:
        #: Given
        recorder = _SnapshotRecorder()
        recorder.record(_path('docs/a'), FileRecord(b'a'))

        #: When
        with pytest.raises(ChangedSnapshotEntryError) as exc_info:
            recorder.record(_path('docs/a/b.md'), FileRecord(b'b'))

        #: Then
        assert exc_info.value.path == _path('docs/a'), 'the error names the file something was found below'
        assert exc_info.value.recorded is EntryKind.FILE, 'the kind recorded first is the file'
        assert exc_info.value.found is EntryKind.DIRECTORY, 'what holds a record is a directory'

    def test_record_of_a_file_above_a_recorded_path_raises_changed_snapshot_entry_error(self) -> None:
        #: Given
        recorder = _SnapshotRecorder()
        recorder.record(_path('docs/a/b.md'), FileRecord(b'b'))

        #: When
        with pytest.raises(ChangedSnapshotEntryError) as exc_info:
            recorder.record(_path('docs/a'), FileRecord(b'a'))

        #: Then
        assert exc_info.value.path == _path('docs/a'), 'the error names the path found as a file'
        assert exc_info.value.recorded is EntryKind.DIRECTORY, 'what holds a record was recorded as a directory'
        assert exc_info.value.found is EntryKind.FILE, 'the kind found later is the file'

    def test_record_of_a_directory_above_a_recorded_path_merges_without_error(self) -> None:
        #: Given
        recorder = _SnapshotRecorder()
        recorder.record(_path('docs/a/b.md'), FileRecord(b'b'))

        #: When
        recorder.record(_path('docs/a'), DirectoryRecord(listed=True))

        #: Then
        assert recorder.to_records() == FrozenMapping(
            {_path('docs/a/b.md'): FileRecord(b'b'), _path('docs/a'): DirectoryRecord(listed=True)}
        ), 'a directory may hold what the scan recorded before it listed the directory'


@pytest.mark.unit
class TestChangedSnapshotEntryError:
    def test_str_with_a_directory_found_as_a_symlink_names_the_path_and_both_kinds(self) -> None:
        #: Given
        error = ChangedSnapshotEntryError(_path('docs/code'), recorded=EntryKind.DIRECTORY, found=EntryKind.SYMLINK)

        #: When
        message = str(error)

        #: Then
        assert 'docs/code' in message, 'the message names the path found as two kinds'
        assert 'directory' in message, 'the message names the kind recorded first'
        assert 'symlink' in message, 'the message names the kind found later'
