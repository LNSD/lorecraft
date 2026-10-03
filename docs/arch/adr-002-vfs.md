---
name: "adr-002-vfs"
description: "The snapshot as the one read of the disk: only the Input package lists, reads or follows a symlink under the workspace root, besides the Composition package finding the root, the snapshot is a value, and a change is the difference between two snapshots. Load when reading a file or listing a directory anywhere, handling filesystem events, or comparing two states of the workspace"
type: "adr"
status: "accepted"
---

# The Snapshot

## Context

The snapshot is the workspace's input to a revision: the state of the tree under the scope, which everything
above the Input package reads instead of the disk.

## Decision

### One Boundary with the Disk

Nothing reads a file, lists a directory or follows a symlink under the workspace root except the Input package
taking a snapshot, and the Composition package finding where the root is. Every other read of the workspace goes
through the snapshot, so two checks behind one report never see two states of the tree.

### The Snapshot Is a Value

A snapshot holds listings, file bytes and symlink targets, and is never patched. The next one is a new value:
a full scan, or the previous snapshot with only the paths that events name scanned again, provided it equals
what a full scan would see. Two snapshots compare structurally, so what changed between two revisions is the
difference between their snapshots. Filesystem events say where and when to look; the change is always computed
from the two states, never from the events.

```python
# ❌ Bad — the change is read off the event stream: an editor's write-then-rename arrives as a delete and a
# create, so a document whose bytes never changed loses every result carried over for it
def on_events(events: list[FsEvent], db: AnalysisDb) -> AnalysisDb:
    return db.without({event.path for event in events})
```

```python
# ✅ Good — the events only say when to look; the change is the difference between two snapshots
def on_events(root: Path, previous: TreeState) -> tuple[TreeState, ChangeList]:
    current = capture(root, SCAN_SCOPE)
    return current, diff_states(previous, current)
```

## Consequences

- Everything above the Input package reads one state of the tree, and only the Input package and the root's
  discovery meet the disk's errors.
- A process that watches the tree rescans the paths events name and compares two snapshots, so an editor's
  write-then-rename never costs a result whose file did not change.

## Checklist

Before committing code, verify:

- [ ] No code reads, lists or follows a symlink under the workspace root, except to take the snapshot or find the root
- [ ] A change between two states is computed from two snapshots, never from filesystem events
- [ ] A snapshot built by rescanning only some paths equals what a full scan of the same tree would see

## References

- [adr-001-snapshot-model](adr-001-snapshot-model.md) - Related: The model and the package roles
- [adr-004-database](adr-004-database.md) - Related: The database that wraps a snapshot
- [principle-validate-at-edge](../code/principle-validate-at-edge.md) - Foundation: The snapshot is the edge, so
  everything above it is trusted values
