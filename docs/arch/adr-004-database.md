---
name: "adr-004-database"
description: "The database of a revision: one report reads one revision, a revision is never updated in place, the view and the cache, and the kinds of query. Load when adding a query, reading the workspace from a check or a command, running work in parallel, or handling a new revision while work is running"
type: "adr"
status: "accepted"
---

# The Database

## Context

The database wraps one revision's inputs and answers every question about them as a query. With its inputs it
makes one revision.

## Decision

### One Report, One Revision

Every check whose result goes into one report reads one revision, so no report describes two states of the tree.
A command analyses one revision, or, in a process that lives across changes, one revision per change, each new
inputs and a new database.

An event of any kind, such as a file saved, a document edited unsaved or an agent's state reported, changes an
input and so produces the next revision. No event updates a derived value directly: what it invalidates follows
from the carry-over rules, applied to the difference between the two revisions' inputs.

A revision is never updated in place. When a new one arrives, work on the old one is abandoned, never patched:
that is how stale work is cancelled. A database's cache is filled from one thread. Reading one revision in
parallel needs a cache that is safe to fill concurrently, added in the change that first runs queries in parallel.

### The View and the Cache

The database is the one object above the Input package that holds the snapshot. A command builds it from the snapshot
it took and hands it to every check of the revision. It has two layers:

- **The view**: the only filesystem view over the snapshot. Every read of the workspace goes through it, and the
  code below the database that reads the workspace reads only the view a query hands it.
- **The cache**: the results of its queries, keyed by what each query was asked, such as a document's ref.

### Every Question Is a Query

A query is a method of the database, computed on first use and memoized until the database is dropped. Its
result is an immutable value. The queries are layered:

- **Structure**: the project model, the index of the scope the snapshot was taken of, and a skill's resource
  listing, the Markdown files inside a skill beside its `SKILL.md` and its symlinks that lead outside the root. They read listings, symlink targets, the
  declared scope and specifications, never a document's content: an edit to a document's text leaves them valid,
  and a retargeted symlink on the way to a skill does not. A resource listing reads only the listings and symlink
  targets its skill's walk reaches, so a change the walk does not reach leaves it valid.
- **Decode**: a file's text, one query per kind of file: a document, a `SKILL.md`, a resource. Each is keyed by
  the file's ref, reads the one file a structure query locates for that ref, the model for a document or a
  `SKILL.md`, its skill's resource listing for a resource, and returns a witness, the ref and its decoded text, or
  an undecodable marker, cached like any answer. It is the one place a file's bytes become text.
- **Per file**: a frontmatter node, a parse tree, a token count, a line count. Each takes the witness its decode
  query returned, never a bare ref, so a fact of an undecodable file cannot be asked for, and is keyed by the
  witness's ref.
- **Fresh**: a question too cheap to keep, such as where a symlink leads, answered on every call and never memoized.

A query reads what it needs through the view, or calls another query to reuse that query's cached result,
then stores its own result in the cache. A reader asks for the cheapest query that holds what it reads: the
frontmatter node, not the parse tree, when it reads only the frontmatter. Readers of one query share one
computation of it.

## Consequences

- No report mixes two states of the tree, and cancelling stale work is dropping a database.
- Running queries in parallel waits for a cache that is safe to fill concurrently; until then, one thread fills a
  database.

## Checklist

Before committing code, verify:

- [ ] No code but the database builds a view over the snapshot; code below it reads only the view a query hands it
- [ ] Every value derived from the snapshot is a query on the database
- [ ] Nothing patches a revision in place; work on an old revision is abandoned when a new one arrives
- [ ] No database's cache is filled from two threads at once
- [ ] An event changes an input and produces a new revision; it never updates a derived value directly

## References

- [adr-001-snapshot-model](adr-001-snapshot-model.md) - Related: The model and the package roles
- [adr-002-vfs](adr-002-vfs.md) - Related: The snapshot the database wraps
- [adr-005-incremental](adr-005-incremental.md) - Related: What a query's result carries over to the next revision
- [pattern-memoization](../code/pattern-memoization.md) - Foundation: How a query is memoized
