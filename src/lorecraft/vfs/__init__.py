"""The filesystem boundary Lorecraft reads through: the views, the disk scan, the snapshot and the change set.

Every argument and answer is spelled as a ``RootRelativePath``, the path type in ``lorecraft.core.path``,
which this package speaks and does not re-export. What a scan reads is the scope its caller passes, a tuple
of ``ScanRoot``; which directories matter is the project model's business, not this package's.
"""

from .changes import Change, ChangeKind, ChangeSet, diff
from .disk import (
    DiskFileSystem,
    ScanRoot,
    SnapshotDirListError,
    SnapshotEntryInspectError,
    SnapshotFileReadError,
    SnapshotLinkReadError,
    disk_location,
    take_snapshot,
)
from .snapshot import FileBytes, Link, Listing, Snapshot, VirtualFileSystem
from .view import (
    DirEntry,
    DirListError,
    DirResolveError,
    EntryInspectError,
    EntryKind,
    FileReadError,
    FileResolveError,
    FileSystem,
    OsRefusal,
    TextDecodeError,
    UnrecordedFileError,
)

__all__ = [
    'FileSystem',
    'DiskFileSystem',
    'disk_location',
    'VirtualFileSystem',
    'Snapshot',
    'Listing',
    'FileBytes',
    'Link',
    'ScanRoot',
    'take_snapshot',
    'SnapshotDirListError',
    'SnapshotEntryInspectError',
    'SnapshotFileReadError',
    'SnapshotLinkReadError',
    'EntryKind',
    'DirEntry',
    'OsRefusal',
    'DirListError',
    'FileReadError',
    'UnrecordedFileError',
    'TextDecodeError',
    'EntryInspectError',
    'DirResolveError',
    'FileResolveError',
    'ChangeKind',
    'Change',
    'ChangeSet',
    'diff',
]
