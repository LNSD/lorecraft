---
name: "adr-003-project-model"
description: "The project model apart from the content: configuration answered from the declared layout, scan roots and agents, content answered from the snapshot, and identity kept apart from location. Load when asking whether a path is in scope, which directories are corpora or skills directories, or where a document's or skill's symlinks lead"
type: "adr"
status: "accepted"
---

# The Project Model

## Context

The project model is what a repository declares: its corpora, meta specs, specs and skills. It answers
from the declaration and the structure of the snapshot, never from what a document says.

## Decision

### The Scope Is Declared, the Content Is Captured

There are two kinds of question, and each has its own source:

- **Configuration**: is this path one the scan reads? Which directories are corpora, which are skills
  directories? These are answered from the declaration — the layout, the scan roots, what the agents state —
  with only the recorded symlinks followed to learn where a path leads.
- **Content**: is there a file here, and what does it say? These are answered from the snapshot.

Never infer configuration from content. A directory that the scope covers but the disk lacks is still in the
scope, so a file named there is missing rather than unknown.

```python
# ❌ Bad — "is this path read by the scan?" answered from what was listed: a directory the scope covers but
# the disk lacks reads as out of scope, so a file named there is reported as unknown instead of missing
def is_read(state: TreeState, path: WorkspacePath) -> bool:
    return path.parent in state.listings
```

```python
# ✅ Good — answered from the declared roots, with recorded symlinks followed to learn where the path leads
def is_read(roots: tuple[ReadRoot, ...], symlinks: tuple[SymlinkRecord, ...], path: WorkspacePath) -> bool:
    entry = _follow_symlinks(symlinks, path.parent) / path.name
    return any(root.covers(entry) for root in _resolved_roots(roots, symlinks))
```

### Identity Is Not Location

A document or a skill is identified by a ref, named where it is listed. Where its symlinks lead is its location,
recorded beside the ref in the model. A symlink retargeted to another file leaves the ref as it was and changes
the location, so whatever is keyed by the ref reads a different file without any bytes changing. A skill resource
is identified by a ref too, and its location is recorded in its skill's resource listing, not in the model.

## Consequences

- A file named in a declared directory that the disk lacks is reported missing, never silently out of scope.
- A retargeted symlink changes a document's location and keeps its ref, so results keyed by the ref follow the file
  it now leads to.

## Checklist

Before committing code, verify:

- [ ] A question about what the scan reads is answered from the declaration, never from what the snapshot holds
- [ ] Code that reads a document's or skill's file reaches it through the location the model records for its ref,
      and a skill resource's through the location its skill's resource listing records

## References

- [adr-001-snapshot-model](adr-001-snapshot-model.md) - Related: The model and the package roles
- [adr-005-incremental](adr-005-incremental.md) - Related: Why location decides whether a result carries over
