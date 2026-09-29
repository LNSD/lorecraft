"""The filesystem boundary Lorecraft reads through: the views, the disk scan, the snapshot and the change set.

Every argument and answer is spelled as a ``RootRelativePath``, the path type this package owns. What a
scan reads is the scope its caller passes, a tuple of ``ScanRoot``; which directories matter is the project
model's business, not this package's.
"""

from .changes import Change, ChangeKind, ChangeSet, diff
from .disk import DiskFileSystem, ScanRoot, TakeSnapshotError, disk_location, take_snapshot
from .path import ROOT, RootRelativePath, RootRelativePathError
from .snapshot import FileBytes, Link, Listing, Snapshot, VirtualFileSystem
from .view import (
    DecodeTextError,
    DirEntry,
    EntryKind,
    FileSystem,
    ListDirError,
    ReadTextError,
    ResolveDirError,
)

__all__ = [
    'RootRelativePath',
    'RootRelativePathError',
    'ROOT',
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
    'TakeSnapshotError',
    'EntryKind',
    'DirEntry',
    'ListDirError',
    'ReadTextError',
    'DecodeTextError',
    'ResolveDirError',
    'ChangeKind',
    'Change',
    'ChangeSet',
    'diff',
]
