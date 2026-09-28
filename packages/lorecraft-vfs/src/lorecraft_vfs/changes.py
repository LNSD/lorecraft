"""What changed between two snapshots, as a value.

A change set is derived from state, never from an event stream: whatever an editor did between two scans (a
write-then-rename, a touch, a three-event save), only the difference between what the two scans saw is
reported. ``diff`` is its only producer.
"""

from dataclasses import dataclass
from enum import Enum
from pathlib import PurePosixPath

from .path import RootRelativePath
from .snapshot import Snapshot


class ChangeKind(Enum):
    """How one path differs between an old snapshot and a new one."""

    ADDED = 'added'
    MODIFIED = 'modified'
    DELETED = 'deleted'


@dataclass(frozen=True, slots=True)
class Change:
    """One path's difference between two snapshots.

    Attributes:
        path: The root-relative path of a listed entry, or of a symlink met on the way to a scope root.
        kind: DELETED also when the entry at ``path`` changed kind; see ``diff``.
    """

    path: RootRelativePath
    kind: ChangeKind


type ChangeSet = frozenset[Change]
"""One batch: unordered, at most one ``Change`` per path."""


def diff(old: Snapshot, new: Snapshot) -> ChangeSet:
    """Compare two snapshots entry by entry. Pure; empty when they are equal.

    Every path ``Snapshot.entries`` reports for either snapshot is compared, so a directory that gains a
    child shows the child ADDED, not the directory MODIFIED. A path only in ``new`` is ADDED; only in
    ``old`` is DELETED; in both with a different kind is DELETED (the entry the model knew is gone, and one
    ``Change`` per path keeps the stronger signal); in both with different bytes, or as a symlink with a
    different target, is MODIFIED; anything else is no change, which is how a touch, a write-then-rename or a
    three-event save collapses to one ``Change`` or none.
    """
    old_entries = old.entries()
    new_entries = new.entries()
    old_bytes = _file_bytes(old)
    new_bytes = _file_bytes(new)
    old_targets = _link_targets(old)
    new_targets = _link_targets(new)

    changes: set[Change] = set()
    for path in old_entries.keys() | new_entries.keys():
        old_kind = old_entries.get(path)
        new_kind = new_entries.get(path)
        if old_kind is None:
            changes.add(Change(path, ChangeKind.ADDED))
        elif new_kind is None or new_kind is not old_kind:
            changes.add(Change(path, ChangeKind.DELETED))
        elif old_bytes.get(path) != new_bytes.get(path) or old_targets.get(path) != new_targets.get(path):
            changes.add(Change(path, ChangeKind.MODIFIED))
    return frozenset(changes)


def _file_bytes(snapshot: Snapshot) -> dict[RootRelativePath, bytes]:
    """The snapshot's file bytes keyed by path."""
    found: dict[RootRelativePath, bytes] = {}
    for file in snapshot.files:
        found[file.path] = file.data
    return found


def _link_targets(snapshot: Snapshot) -> dict[RootRelativePath, PurePosixPath]:
    """The snapshot's symlink targets keyed by the link's path."""
    found: dict[RootRelativePath, PurePosixPath] = {}
    for link in snapshot.links:
        found[link.path] = link.target
    return found
