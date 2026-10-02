---
name: "module-lorecraft-vfs"
description: "The lorecraft.vfs package's responsibility, role, boundary and invariants: the one boundary with the disk, the snapshot as a value, views that answer from it, and change sets between two of them. Load when adding or moving code in lorecraft.vfs, reading a file or listing a directory anywhere, or adding a question about paths, symlinks or scan roots"
type: "pkg"
scope: "pkg:lorecraft.vfs"
---

# The `lorecraft.vfs` Package

## Responsibility

Be the one boundary between Lorecraft and the files under the workspace root. It changes when the way the disk is
read changes, or the way a captured state of it is represented.

## Role

**Input.** It reads the disk once, into a snapshot, and every package above it reads through a view that answers
from that snapshot. It reads what its caller declares: the scope arrives as scan roots that the caller passes in,
and the package never knows why those directories matter or what the files in them mean.

## Belongs Here

- Code that lists a directory, reads a file's bytes or reads a symlink's target under the workspace root.
- The snapshot, its parts, and the code that builds one, from the disk or by hand.
- The view contract, and each view that answers it, from the disk or from a snapshot.
- Following a chain of symlinks to where it leads, and refusing the ones that leave the root.
- The shape of a scan root, and questions answered from a scope plus the symlink chains a snapshot recorded.
- The difference between two snapshots.

## Belongs Elsewhere

| Code that… | Belongs in |
|---|---|
| Names `docs/`, a skills directory or any other fixed directory | `lorecraft.layout` |
| Decides which directories a snapshot reads | `lorecraft.layout`, as the scope it declares |
| Decides what an entry is to Lorecraft: a document, a specification, a skill | `lorecraft.project` |
| Parses or decodes the bytes of a file | `lorecraft.project` |
| Keeps a value derived from a file for the snapshot's lifetime | `lorecraft.checks` |
| Finds the workspace root, or maps a command-line argument onto it | `lorecraft.cli` |

## Invariants

- A snapshot is an immutable value. It holds listings, bytes and symlink targets, and never a handle, a stat result
  or an mtime, so two snapshots compare and hash structurally.
- Every path crossing the boundary is root-relative. The root is joined to a path only inside this package, and
  every answer leaves root-relative again.
- Code above reads through the view contract and never names a concrete view, except the code that builds one.
  For every operation of the contract, and every path whose symlinks stay under the root, the snapshot view
  answers as the disk view does. A question only one view can answer stays off the contract, on that view, and
  only code that names that view asks it.

## Examples

```python
# ❌ Bad — the boundary hard-codes the layout: a new corpus directory edits the input layer, and a test that
# captures any other tree still scans docs/
def capture(root: Path) -> TreeState:
    return _scan(root, roots=(ReadRoot(WorkspacePath.parse('docs'), depth=1),))
```

```python
# ✅ Good — the caller declares the scope; the boundary reads what it is told
def capture(root: Path, roots: tuple[ReadRoot, ...]) -> TreeState:
    return _scan(root, roots=roots)
```

## Checklist

Before committing code, verify:

- [ ] Nothing added to `lorecraft.vfs` names a directory of the layout or a kind of document
- [ ] A new snapshot field is immutable and holds no handle, stat result or mtime
- [ ] Every new argument and answer is root-relative, and no `Path` crosses the boundary
- [ ] A new contract operation answers alike on both views for paths under the root; one only a single view can
      answer lives on that view, off the contract

## References

- [arch-snapshot-model](arch-snapshot-model.md) - Foundation: The Input role
- [arch-vfs](arch-vfs.md) - Foundation: The one boundary with the disk, and the snapshot as a value
- [arch-project-model](arch-project-model.md) - Foundation: The scope is declared, and symlinks decide where a
  path leads
- [principle-single-responsibility](principle-single-responsibility.md) - Foundation: One reason to change
- [principle-validate-at-edge](principle-validate-at-edge.md) - Foundation: The boundary is where paths are
  proved root-relative
