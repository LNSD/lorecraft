"""What changed between two snapshots, as a value.

A change set is derived from state, never from an event stream: whatever an editor did between two scans (a
write-then-rename, a touch, a three-event save), only the difference between what the two scans saw is
reported. ``diff`` is its only producer.
"""

from dataclasses import dataclass
from enum import Enum
from typing import assert_never

from lorecraft.core.path import ROOT, RootRelativePath

from .snapshot import DirectoryRecord, FileRecord, OtherRecord, Snapshot, SymlinkRecord


class ChangeKind(Enum):
    """How one path differs between an old snapshot and a new one."""

    ADDED = 'added'
    MODIFIED = 'modified'
    DELETED = 'deleted'


@dataclass(frozen=True, slots=True)
class Change:
    """One path's difference between two snapshots.

    Attributes:
        path: The root-relative path of any record but the root's: a listed entry, a listed directory, a file a
            followed link leads to, a symlink met along a chain, or a directory climbed out of.
        kind: DELETED also when the entry at `path` changed kind; see `diff`.
    """

    path: RootRelativePath
    kind: ChangeKind


type ChangeSet = frozenset[Change]
"""One batch: unordered, at most one ``Change`` per path."""


def diff(old: Snapshot, new: Snapshot) -> ChangeSet:
    """Compare two snapshots record by record. Pure; empty when they are equal.

    Every path either snapshot records is compared, the root aside, so a directory that gains a child shows the
    child ADDED, not the directory MODIFIED. A path only in `new` is ADDED; only in `old` is DELETED; in both with
    a different kind is DELETED (the entry the model knew is gone, and one `Change` per path keeps the stronger
    signal); in both as a file with different bytes, or as a symlink with a different target, is MODIFIED; anything
    else is no change, which is how a touch, a write-then-rename or a three-event save collapses to one `Change` or
    none. A directory's flags are not compared: whether the scan listed it or climbed out of it says how the scan
    reached it, not what is there.

    The scopes are not compared, since a change set names paths and a scope is no path: what a wider or a
    narrower scope reads shows as the entries it adds or drops. So an empty change set does not mean equal
    snapshots; whether the declaration changed is `old.scope != new.scope`.

    Args:
        old: The earlier snapshot, the state the model last knew.
        new: The later snapshot; paths only it records are ADDED.
    """
    changes: set[Change] = set()
    for path in old.records.keys() | new.records.keys():
        if path == ROOT:
            continue  # the root always exists; whether a scan listed it is a matter of scope
        old_record = old.records.get(path)
        new_record = new.records.get(path)
        if old_record is None:
            changes.add(Change(path, ChangeKind.ADDED))
            continue
        if new_record is None or new_record.kind is not old_record.kind:
            changes.add(Change(path, ChangeKind.DELETED))
            continue
        # The same kind on both sides, so only what that kind records can differ.
        match new_record:
            case DirectoryRecord():
                pass  # a directory's flags are not compared; see the docstring
            case FileRecord() | SymlinkRecord() | OtherRecord():
                if new_record != old_record:  # a file's bytes or a link's target; an other entry records nothing
                    changes.add(Change(path, ChangeKind.MODIFIED))
            case _:
                assert_never(new_record)
    return frozenset(changes)
