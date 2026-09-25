---
name: "pattern-transaction-boundary"
description: "Group related writes in one boundary that commits them together or leaves nothing behind, with a visible owner of commit, rollback and close. Load when several writes must succeed or fail together, when rewriting a file in place, or when using a sqlite3 connection as a context manager"
type: "core"
scope: "global"
---

# Transaction Boundary (All or Nothing)

## Rule

When several writes are only meaningful together, make them one unit: either all become visible or none do. A
reader of the store must never observe half of the unit, and a failure partway through must leave the state it
started from.

Put the boundary where the unit of meaning is, in the code that knows which writes belong together, not in each
low-level write helper. One function owns the boundary and states, by its structure, who commits, who rolls
back, and who closes the underlying resource. Those are three distinct responsibilities; a construct that does
one of them does not do the others.

Two Python forms cover the common cases:

- **A database connection.** `with connection:` on a `sqlite3.Connection` commits on success and rolls back on
  an exception. It does not close the connection, and it does not open one. Close separately, with
  `contextlib.closing` or the owning lifecycle
  ([pattern-resource-lifecycle](pattern-resource-lifecycle.md)).
- **A file.** Rewrite a file by writing the new content to a temporary file in the same directory, then
  `os.replace` it over the original. The replace is atomic on the same filesystem, so a reader sees the old
  file or the new one, never a truncated one. Remove the temporary file on failure.

## Examples

1. **Rewriting a document in place**
   A fix mode rewrites a document's frontmatter.

```python
# ❌ Bad — `write_text` truncates first; an error while rendering the body leaves an empty
# document on disk, and the watcher reports it as a new finding.
def rewrite_document(path: Path, header: str, body: str) -> None:
    path.write_text(header + render(body))
```

```python
# ✅ Good — the new content is complete before it replaces the old; a failure leaves the
# original untouched and no stray temporary file.
def rewrite_document(path: Path, header: str, body: str) -> None:
    content = header + render(body)
    staged = tempfile.NamedTemporaryFile('w', dir=path.parent, delete=False)
    try:
        with staged:
            staged.write(content)
        os.replace(staged.name, path)
    except BaseException:
        os.unlink(staged.name)
        raise
```

2. **Committing without closing**

```python
# ❌ Bad — `with connection` committed the findings but never closed the connection,
# which stays open until garbage collection.
def store_findings(db_path: Path, findings: list[Finding]) -> None:
    connection = sqlite3.connect(db_path)
    with connection:
        connection.execute('DELETE FROM findings')
        connection.executemany('INSERT INTO findings VALUES (?, ?)', rows(findings))
```

```python
# ✅ Good — `closing` owns the connection's lifetime; the inner block owns the transaction.
def store_findings(db_path: Path, findings: list[Finding]) -> None:
    with contextlib.closing(sqlite3.connect(db_path)) as connection:
        with connection:
            connection.execute('DELETE FROM findings')
            connection.executemany('INSERT INTO findings VALUES (?, ?)', rows(findings))
```

## Why It Matters

A partial write is worse than a failed one: the failure is reported once, but the half-written state is read
by every later run. A single boundary makes the unit of meaning visible in the code and gives failure one
outcome, the previous state. Separating commit from close prevents the common reading that a `with` block
cleaned up everything.

## Pragmatism Caveat

A single write that the store already applies atomically needs no extra boundary. Output nobody reads back,
such as a report streamed to stdout, is not a transaction. Do not widen a boundary to include slow work that
does not write, which holds locks longer for nothing.

## Checklist

- [ ] Writes that belong together share one commit/rollback boundary
- [ ] The boundary sits where the unit of meaning is, not in each write helper
- [ ] A `sqlite3` connection used as a context manager is also closed by its owner
- [ ] A file rewritten in place is staged in the same directory and moved with `os.replace`
- [ ] A failure leaves the original state and no staged file behind

## References

- [pattern-resource-lifecycle](pattern-resource-lifecycle.md) - Related: Owns closing the resource the transaction runs on
- [python-paths](python-paths.md) - Related: Owns how file paths are built and passed

## External References

- [Python docs — sqlite3 connection as a context manager](https://docs.python.org/3.12/library/sqlite3.html#how-to-use-the-connection-context-manager)
- [Python docs — `os.replace`](https://docs.python.org/3.12/library/os.html#os.replace)
