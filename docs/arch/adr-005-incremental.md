---
name: "adr-005-incremental"
description: "Incremental computation across revisions and processes: each query's carry-over rule, early cutoff for a result recomputed unchanged, no cache of snapshot-derived values outside the database, results persisted for warm starts, and results as persistable data. Load when adding a cache, a query or a persisted store, or making a query result carry over to the next revision"
type: "adr"
status: "accepted"
---

# Incremental Computation

## Context

A database lives for one revision, but its results need not. The next database may keep every result the change
left valid, and a new process may start from results an earlier one stored.

## Decision

### Results Carry Over Between Revisions

Each query states its **carry-over rule** in its own docstring: the changes between two revisions' inputs that
invalidate it, so the next database can keep every result the rule leaves valid. The database's module docstring
keeps only what holds for every query. A per-file result carries over only when its file's location and bytes
are both unchanged: a retargeted symlink changes no bytes, but changes the file.

A result recomputed for the next revision that equals the previous one leaves every result built from it valid.
An edit to a document's prose recomputes its parse tree, but leaves its frontmatter node equal, so whatever reads
only the frontmatter carries over.

A cache of anything derived from the snapshot, kept anywhere else, has no rule and outlives its snapshot. A
resource built from the package's own data, such as a tokenizer's vocabulary, reads no workspace and may be
cached for the process.

```python
# ❌ Bad — the parse keeps its own cache: it is keyed on the path, so it serves the old tree after the file
# changes, in a process that holds two snapshots
_TREES: dict[WorkspacePath, DocumentTree] = {}


def parse(path: WorkspacePath, text: str) -> DocumentTree:
    return _TREES.setdefault(path, _build_tree(text))
```

```python
# ✅ Good — the parse is a pure function of the text; the per-snapshot query decides when to call it again
def parse(text: str) -> DocumentTree:
    return _build_tree(text)
```

### Results Persist Across Processes

A result persisted across processes is a carry-over too: keyed by the identity, location and content hash it was
computed from, and kept only once the database validates it against the new revision's inputs by the same
rule. Only the
database reads or writes the store, which lives outside the workspace root and so never enters a snapshot.

So every query result is data a store can write and a new database can reload: immutable values, tuples, frozen
records and read-only mappings, holding no handle, callable, compiled third-party object or reference back to the
database. Whatever a result needs that is not data, such as a compiled validator, is rebuilt from it on use.

## Consequences

- Every query states its carry-over rule, so a later process can keep each result a change left valid.
- No snapshot-derived cache lives outside the database, and every query result stays persistable data, so warm
  starts need no redesign of the results.

## Checklist

Before committing code, verify:

- [ ] No cache of a value derived from the snapshot lives outside the database
- [ ] A new query result is persistable data: no handle, callable, compiled third-party object or database reference

## References

- [adr-001-snapshot-model](adr-001-snapshot-model.md) - Related: The model and the package roles
- [adr-004-database](adr-004-database.md) - Related: The queries whose results carry over
- [adr-003-project-model](adr-003-project-model.md) - Related: Identity apart from location
- [adr-012-database-derivation](adr-012-database-derivation.md) - Related: The package the database, and so its
  caches, live in
- [pattern-memoization](../code/pattern-memoization.md) - Foundation: How a query is memoized
