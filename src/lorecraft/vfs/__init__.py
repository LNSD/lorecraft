"""The filesystem boundary Lorecraft reads through: the views, the disk scan, the snapshot, scope and change set.

Every argument and answer is spelled as a `RootRelativePath`, the path type in `lorecraft.core.path`,
which this package speaks and does not re-export. What a scan reads is the scope its caller passes, a tuple
of `ScanRoot` the snapshot records, and a `ScopeIndex` built once from it answers from that declaration whether
a scan of it reads a path; which directories matter is the project model's business, not this package's.
"""

from .changes import Change, ChangeKind, ChangeSet, diff
from .disk import (
    DiskFileSystem,
    SnapshotDirListError,
    SnapshotEntryInspectError,
    SnapshotFileReadError,
    SnapshotLinkReadError,
    disk_location,
    take_snapshot,
)
from .scan_root import ScanRoot
from .scope import ScopeIndex
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
    'ScopeIndex',
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
