"""Snapshots built by hand from a tree of file bytes, for tests that need no disk."""

from collections.abc import Mapping
from typing import assert_never

from lorecraft.core.path import ROOT, PathComponent, RootRelativePath
from lorecraft.vfs import DirectoryRecord, EntryRecord, FileRecord, Snapshot, SnapshotRecords

type FileTree = Mapping[str, bytes | FileTree]
"""A directory's contents: each key one entry's name, mapped to a file's bytes or to a directory's own contents."""


def from_tree(tree: FileTree) -> Snapshot:
    """Build a snapshot from a tree of directories and file bytes, every directory in it listed.

    Every mapping in the tree is a listed directory, the root `.` included, so `from_tree({})` lists the
    root with no entries and an empty mapping under a name is an empty directory. Nothing was scanned, so the
    scope is empty and no path is in it, the listed directories included.

    Args:
        tree: The root's contents: each key is one entry's name, mapped to its bytes for a file or to the
            directory's own contents for a directory. Bytes are kept as given.

    Raises:
        PathComponentError: If a key is empty, is `.` or `..`, or holds a `/`.
    """
    records: dict[RootRelativePath, EntryRecord] = {ROOT: DirectoryRecord(listed=True)}
    _record_tree(ROOT, tree, records)
    return Snapshot(SnapshotRecords(records), scope=())


def _record_tree(directory: RootRelativePath, tree: FileTree, records: dict[RootRelativePath, EntryRecord]) -> None:
    """Record every entry of `directory` and everything below it, for `from_tree`.

    Args:
        directory: The root-relative directory `tree` holds the contents of, already recorded as listed.
        tree: The directory's contents, each key one entry's name.
        records: The records taken so far, keyed by path; one is added for each entry in or below `directory`.

    Raises:
        PathComponentError: If a key is empty, is `.` or `..`, or holds a `/`.
    """
    for raw_name, node in tree.items():
        path = directory / PathComponent.parse(raw_name)
        match node:
            case bytes():
                records[path] = FileRecord(node)
            case Mapping():
                records[path] = DirectoryRecord(listed=True)
                _record_tree(path, node, records)
            case _:
                assert_never(node)
