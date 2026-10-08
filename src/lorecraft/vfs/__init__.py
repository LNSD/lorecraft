"""The filesystem boundary Lorecraft reads through: the views, the disk scan, the snapshot, scope and change set.

Every argument and answer is spelled as a `RootRelativePath`, the path type in `lorecraft.core.path`,
which this package speaks and does not re-export. A path the views resolve, with every symlink followed, is
a `ResolvedPath`, this package's own static distinction over it. What a scan reads is the scope its caller
passes, a tuple of `ScanRoot` the snapshot records, and a `ScopeIndex` built once from it answers from that
declaration whether a scan of it reads a path; which directories matter is the project model's business, not
this package's.
"""

from .changes import Change, ChangeKind, ChangeSet, diff
from .disk import (
    ChangedSnapshotEntryError,
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
from .snapshot import (
    DirectoryRecord,
    EntryRecord,
    FileRecord,
    FileTree,
    OtherRecord,
    Snapshot,
    SymlinkRecord,
    VirtualFileSystem,
)
from .utf8_failure import Utf8Failure, Utf8Reason
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
    ResolvedPath,
    RootExit,
    TextDecodeError,
    UnrecordedFileError,
)

__all__: list[str] = [
    'FileSystem',
    'ResolvedPath',
    'DiskFileSystem',
    'disk_location',
    'VirtualFileSystem',
    'Snapshot',
    'FileTree',
    'EntryRecord',
    'DirectoryRecord',
    'FileRecord',
    'SymlinkRecord',
    'OtherRecord',
    'ScanRoot',
    'ScopeIndex',
    'take_snapshot',
    'SnapshotDirListError',
    'SnapshotEntryInspectError',
    'SnapshotFileReadError',
    'SnapshotLinkReadError',
    'ChangedSnapshotEntryError',
    'EntryKind',
    'DirEntry',
    'RootExit',
    'OsRefusal',
    'DirListError',
    'FileReadError',
    'UnrecordedFileError',
    'TextDecodeError',
    'Utf8Failure',
    'Utf8Reason',
    'EntryInspectError',
    'DirResolveError',
    'FileResolveError',
    'ChangeKind',
    'Change',
    'ChangeSet',
    'diff',
]
