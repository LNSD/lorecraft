"""What changed between two snapshots, as a value.

A change set is derived from state, never from an event stream: whatever an editor did between two scans (a
write-then-rename, a touch, a three-event save), only the difference between what the two scans saw is
reported. ``diff`` is its only producer.
"""

from enum import Enum
from typing import assert_never

from lorecraft.core.mapping import FrozenMapping
from lorecraft.core.path import ROOT, RootRelativePath

from .snapshot import (
    DirectoryRecord,
    FileRecord,
    OtherRecord,
    RefusedInspect,
    RefusedListing,
    RefusedRead,
    Snapshot,
    SymlinkRecord,
)


class ChangeKind(Enum):
    """How one path differs between an old snapshot and a new one."""

    ADDED = 'added'
    MODIFIED = 'modified'
    DELETED = 'deleted'


type ChangeSet = FrozenMapping[RootRelativePath, ChangeKind]
"""One batch: each changed path with how it differs, so a path has at most one change.

A key is the root-relative path of any record but the root's: a listed entry, a listed directory, a file a followed
link leads to, a symlink met along a chain, or a directory climbed out of. The kind is DELETED also when the entry at
the path changed kind, and MODIFIED also when the scan gained or lost a refusal at it; see `diff`.
"""


def diff(old: Snapshot, new: Snapshot) -> ChangeSet:
    """Compare two snapshots record by record. Pure; empty when they are equal.

    Every path either snapshot records is compared, the root aside, so a directory that gains a child shows the
    child ADDED, not the directory MODIFIED. A path only in `new` is ADDED; only in `old` is DELETED; in both with
    a different kind is DELETED (the entry the model knew is gone, and one entry per path keeps the stronger
    signal); in both as a file with different bytes, or as a symlink with a different target, is MODIFIED; in both
    with the operating system's refusal kept at one and not at the other, such as a directory the scan could not list
    that it now can, or a file it could not read that it now can, is MODIFIED; anything else is no change, which is
    how a touch, a write-then-rename or a three-event save collapses to one entry or none. A directory's flags
    are not compared: whether the scan listed it or climbed out of it says how the scan reached it, not what is
    there.

    The scopes are not compared, since a change set names paths and a scope is no path: what a wider or a
    narrower scope reads shows as the entries it adds or drops. So an empty change set does not mean equal
    snapshots; whether the declaration changed is `old.scope != new.scope`.

    Args:
        old: The earlier snapshot, the state the model last knew.
        new: The later snapshot; paths only it records are ADDED.
    """
    changes: dict[RootRelativePath, ChangeKind] = {}
    for path in old.records.keys() | new.records.keys():
        if path == ROOT:
            continue  # the root always exists; whether a scan listed it is a matter of scope
        old_record = old.records.get(path)
        new_record = new.records.get(path)
        if old_record is None:
            changes[path] = ChangeKind.ADDED
            continue
        if new_record is None or new_record.kind is not old_record.kind:
            changes[path] = ChangeKind.DELETED
            continue
        # The same kind on both sides, so only what that kind records can differ.
        match new_record:
            case DirectoryRecord():
                # A directory's flags are not compared; see the docstring. One the scan could not list before is
                # another thing: its entries are known now.
                if isinstance(old_record, RefusedListing):
                    changes[path] = ChangeKind.MODIFIED
            case RefusedListing():
                if not isinstance(old_record, RefusedListing):
                    changes[path] = ChangeKind.MODIFIED
            case FileRecord() | SymlinkRecord() | OtherRecord() | RefusedRead() | RefusedInspect():
                # A file's bytes or a link's target; what was refused, or that it was read or refused at all;
                # an other entry records nothing.
                if new_record != old_record:
                    changes[path] = ChangeKind.MODIFIED
            case _:
                assert_never(new_record)
    return FrozenMapping(changes)
