---
name: "adr-015-database"
description: "The database of a revision, opened with its model: one report reads one revision, a revision is never updated in place, the view and the cache, the kinds of query, a model that records what failed to load as values, and skip or partial as the consumer's policy. Load when adding a query, opening or advancing a database, reading the workspace from a check or a command, handling a load failure, running work in parallel, or handling a new revision while work is running"
type: "adr"
status: "accepted"
---

# The Database, Opened with Its Model

> [!NOTE]
> Supersedes [adr-004-database](adr-004-database.md): its revisions, view, cache and kinds of query, restated here
> unchanged except for how the model is loaded. adr-004 binds no code.

## Context

The database wraps one revision's inputs and answers every question about them as a query. With its inputs it makes
one revision. [adr-004](adr-004-database.md) made every query, the project model included, a method computed on first
use.

Loading the model fails as a whole today. Any error on the way aborts the load: a structure file that cannot be
read or is invalid, a corpus or a directory under `docs/` that cannot be listed, a skills directory, skill entry or
`SKILL.md` that cannot be resolved. Because the model loads on first use, every query that reaches it, directly or
through `governance(ref)`, can be the call that triggers the load. So every per-document query lists every one of the
load's errors, each "if the model is not loaded yet". A database whose model has not loaded can be represented, and
every query has to answer for that state. In practice every command loads the model before any per-document query
runs, so the laziness buys nothing.

[prd-014](prd-014-resilient-model-loading.md) asks for the opposite of a load that fails as a whole: each failure
reported where it happened, and everything it does not touch checked (FR-001 to FR-009). It also asks for one model
that serves two consumers. A check run skips a document governed by a failed meta spec (FR-010). An LSP-style mode
checks it against the meta specs that loaded and labels the result partial (FR-012).

## Decision

### One Report, One Revision

Every check whose result goes into one report reads one revision, so no report describes two states of the tree. A
command analyses one revision, or, in a process that lives across changes, one revision per change, each new inputs
and a new database.

An event of any kind, such as a file saved, a document edited unsaved or an agent's state reported, changes an input
and so produces the next revision. No event updates a derived value directly: what it invalidates follows from the
carry-over rules, applied to the difference between the two revisions' inputs.

A revision is never updated in place. When a new one arrives, work on the old one is abandoned, never patched: that is
how stale work is cancelled. A database's cache is filled from one thread. Reading one revision in parallel needs a
cache that is safe to fill concurrently, added in the change that first runs queries in parallel.

### A Database Is Opened with Its Model

1. **`Database.from_snapshot(snapshot)` is the only way to get a database for a snapshot**, and the reserved
   `advance(snapshot)` the only way to get the next one. `from_snapshot` builds the view, refuses a linked layout, loads
   the model through the view, and constructs the database from the view and the model; the view carries its snapshot,
   so the snapshot is not passed beside it. `advance` will do the same for the next revision, carrying the model over or
   loading it again by its carry-over rule.
2. **A database always holds its model.** The model is not optional on the database, and `model()` returns it and
   raises nothing. A database whose model has not loaded cannot be represented. The model is the one structure value
   loaded at open; every other query is still computed on first use.
3. **What `from_snapshot` raises is limited to what makes a model impossible**: a linked `docs/` or `docs/__meta__/`, as
   today. A failure inside the declaration is never raised (see below).

Python has no private constructor, so code could call the constructor with a model loaded through another view. The
design states the gap rather than guard it, as [adr-011](adr-011-rules-engine.md) does for a decode witness: only
`from_snapshot` and `advance` construct a database, and a test or a command that needs one calls `from_snapshot`.

### Load Failures Are Values the Model Records

1. **The loader is total over the model's structural declaration.** Each structural unit it reads is loaded on its
   own: a structure file, a corpus directory, a skills directory, a skill entry, a skill's `SKILL.md`. A unit that
   fails is recorded in the model as a load failure, and the loader goes on with the next unit. The snapshot
   declaration also retains unreadable regular files under `docs/`; the database exposes refusals not represented
   by model load failures as a query result, so check and future workspace consumers can report them without a
   second scan. Neither `load_model` nor any query raises a model-load error (FR-009).
2. **A failure is recorded per meta spec layer.** A corpus meta spec or a namespace meta spec whose structure file
   fails holds the failure where it would hold its structure: `structure: StructureSpec | FailedStructure | None`. So
   a document's governance holds each layer as loaded or failed, in the layer order
   [adr-016](adr-016-specifications.md) fixes.
3. **Every load failure is also listed once on the model**, with its path and its condition, whatever its origin: a
   structure file, a corpus directory, a skills directory, a skill entry or a `SKILL.md`. This list is what the run
   reports (FR-006).
4. **A recorded failure is data, never an exception.** It is a frozen record of the facts the error carries, such as
   the path, the operating system's refusal or the decoder's problems, without the foreign exception the error wraps.
   There is one record type per condition, in one closed union, so a reader matching it is checked exhaustive. A
   record compares by value and persists like any query result ([adr-005](adr-005-incremental.md)).
5. **The model decides no policy.** It records what loaded and what failed. Whether a document governed by a failed
   layer is skipped or judged partially is decided by the consumer that reads the model.

```python
@dataclass(frozen=True, slots=True)
class FailedStructure:
    """A structure file that could not be read or used; it stands in the layer where its structure would."""

    path: RootRelativePath
    failure: StructureLoadFailure    # the closed union of the conditions a structure file fails with


@dataclass(frozen=True, slots=True)
class Governance:
    ref: DocumentRef
    corpus_spec: CorpusSpec          # its `structure` may be a FailedStructure
    namespace_specs: tuple[NamespaceSpec, ...]

    def failed_layers(self) -> tuple[FailedStructure, ...]: ...
```

Names in the sketches are illustrative; the shapes are the decision.

### Where a Load Failure Becomes a Diagnostic

1. **A load failure is an engine condition** ([adr-009](adr-009-rules.md)): a code in the engine's group, a fixed
   error severity, no level, and a rulebook page. No configuration or selection turns it off (FR-007, FR-008, FR-016).
2. **It is reported once, at its own path.** The run turns each failure the model lists into an engine diagnostic in
   a report of its own, filed at the failure's path: the structure file, the directory or the skill entry. The report
   joins the subject reports in the one total order of [adr-010](adr-010-diagnostics.md) (FR-001 to FR-004, FR-006).
3. **The exit code follows from the severity.** A load failure or a retained refusal reported as an error diagnostic
   makes a check run exit 1 (FR-014). What stops the run before any report, such as root discovery, an invalid
   selection, a linked layout or a refusal outside the declaration the snapshot cannot retain, still exits 2
   (FR-015). An unreadable document under `docs/` is retained by the snapshot, exposed by the database and reported
   as `LC002`; it remains a subject even though no rule can read it. A refusal on a skill link the snapshot follows
   to reach a skill unit still exits 2, since no model load failure or declared-document refusal stands for it yet
   (prd-014 Edge Cases).
4. **A documentation root or meta spec directory that cannot be listed stops the run** (FR-005). The model still
   records it as a value, a load failure like any other, so the database is opened and nothing raises. The command
   reads it before selecting any subject, prints it as a failure and exits 2, as it does when the root cannot be
   found. With no corpus and no meta spec known, a report over what remained would read as a clean result for a
   workspace that was never checked. The command makes this choice, not the model, so the LSP-style mode can still
   open the database and report the failure in its own way.

### Skip or Partial Is the Consumer's Policy

1. **The database hands out what loaded and what failed, and nothing more.** `governance(ref)` returns the layers
   as they are. An analysis that reads governance, such as `schema_problems` or `outline_divergences`, reads only the
   layers that loaded. That is a fact about those layers and not a verdict on the document.
2. **The check run skips.** Its entry point gives a document whose governance holds a failed layer no rule. It reports the
   document as skipped in coverage, naming each failed layer's structure file (FR-010, FR-011). The document is still
   decoded first, so a file that cannot be decoded is reported as it is today.
3. **The LSP-style mode will judge partially.** It will have an entry point of its own beside the check run's, over
   the same shared runner, that runs the rules over the layers that loaded and labels the result partial (FR-012).
   It is not built until the mode exists. Nothing below the entry points changes for it, since the database already
   hands out both kinds of layer.

   The policy is one entry point per mode over the shared runner: no policy parameter and no callback, so a new
   mode edits neither the shared runner nor another mode.

### The View and the Cache

The database is the one object above the Input package that holds the snapshot. A command opens it from the snapshot
it took and hands it to every check of the revision. It has two layers:

- **The view**: the only filesystem view over the snapshot. Every read of the workspace goes through it, and the code
  below the database that reads the workspace reads only the view a query hands it.
- **The cache**: the results of its queries, keyed by what each query was asked, such as a document's ref.

### Every Question Is a Query

A query is a method of the database, memoized until the database is dropped. Its result is an immutable value. The
model is loaded when the database is opened; every other query is computed on first use. The queries are layered:

- **Structure**: the project model, the index of the scope the snapshot was taken of, a document's governance,
  `governance(ref)`, what the model states governs one document, and a skill's resource listing, the Markdown files
  inside a skill beside its `SKILL.md` and its symlinks that lead outside the root. They read listings, symlink
  targets, the declared scope and meta specs, never a document's content: an edit to a document's text leaves them
  valid, and a retargeted symlink on the way to a skill does not. A resource listing reads only the listings and
  symlink targets its skill's walk reaches, so a change the walk does not reach leaves it valid. A document's
  governance is kept whenever it is recomputed equal, a failed layer compared by its recorded failure, so a model
  change that leaves it equal leaves valid every query that reads it.
- **Decode**: a file's text, one query per kind of file: a document, a `SKILL.md`, a resource. Each is keyed by the
  file's ref and reads the one file a structure query locates: the model locates a document or a `SKILL.md` by its
  ref, and the resource decode takes the location its skill's resource listing issued. Each returns a witness, the
  ref and its decoded text, or an undecodable marker, cached like any answer. It is the one place a file's bytes
  become text: an excerpt of a document, a `SKILL.md` or a resource, rendered for a diagnostic, is cut from the text
  its decode query returned, never from a second decode of the file.
- **Per file**: a frontmatter node, a parse tree, a token count, a line count. Each takes the witness its decode query
  returned, never a bare ref, so a fact of an undecodable file cannot be asked for, and is keyed by the witness's ref.
- **Analysis**: a shared analysis of one file against what governs it, which several rules read: `schema_problems`,
  what each governing frontmatter schema rejects in a document's frontmatter, `skill_schema_problems`, the same for a
  skill against the Agent Skills specification, and `outline_divergences`, where a document's sections first stop
  matching each governing outline. Each takes the witness, reads the per-file queries it analyses and, for a
  document, its governance through `governance(ref)`, never the whole model, and is kept whenever they are: a model
  change that leaves a document's governance equal keeps its analyses. It finds problems, not diagnostics: levels
  apply after detection, so no diagnostic is cached.
- **Cross-file**: `link_targets`, `skill_link_targets` and `skill_resource_link_targets`, what the snapshot holds at
  the target of each relative link of a document, a `SKILL.md` or a resource: present, missing or outside the scope,
  each entry also keeping the root-relative path it was looked up at. Each takes the witness, reads the file's parse
  and, for each path a link names, the snapshot's records on the way to it and the scope, and is kept only when the
  parse is kept and every path it looked up, an absent target included, resolves the same and is in the same scope
  state.
- **Fresh**: a question too cheap to keep, such as where a symlink leads, answered on every call and never memoized.

A query reads what it needs through the view, or calls another query to reuse that query's cached result, then stores
its own result in the cache. A reader asks for the cheapest query that holds what it reads: the frontmatter node, not
the parse tree, when it reads only the frontmatter. Readers of one query share one computation of it.

### Carry-Over of a Recorded Failure

A recorded failure is part of the model, so it carries over exactly when the model does, by the model's carry-over
rule ([adr-005](adr-005-incremental.md)). A changed structure file invalidates the model, and with it the failure
recorded for that file, as it would a structure that loaded. An entry added or deleted under `docs/`, or in the skills
layout, does the same. A failure recomputed for the next revision that equals the previous one, the same path and the
same condition, leaves every governance that holds it equal. So the documents it governs keep their skipped state and
their analyses without being looked at again.

## Consequences

- **The per-document `Raises:` blocks shrink.** The model's load errors leave every query that reads the model or
  a document's governance, the runner and the subject selection. `model()` and `load_model` raise
  nothing for the declaration. `Database.from_snapshot` raises only the linked-layout refusal.
- **A broken meta spec no longer stops a check run.** It is an error diagnostic on its structure file, and the
  documents it governs are skipped and listed in coverage.
- **Two other records change with this one, so no two accepted records contradict each other.**
  [adr-006](adr-006-specifications.md) says a meta spec that cannot be loaded is a failure of the run. It is
  restated in [adr-016](adr-016-specifications.md), which supersedes it and was accepted together with this record.
  [adr-010](adr-010-diagnostics.md) keeps its decision; its example of a failure that exits 2 is now a `docs/` that
  cannot be listed instead of a meta spec that cannot be loaded.
- **Every caller opens the database.** The two commands and the tests that build a database call
  `Database.from_snapshot`, and nothing reads the model before it.
- **The loader catches what it reads, unit by unit.** Each repository still raises its own error variant. The loader
  catches the variants of one unit, records the facts, and goes on: a handler that degrades, which
  [error-handling](../code/error-handling.md) allows.
- **The run reports a new kind of report**, a load failure at its path, and a new coverage reason, skipped. The text
  and the machine-readable output carry both, which is an output change for the release notes.
- **What stays true:** one report reads one revision, a revision is never patched, every other query is computed on
  first use, and every query result is persistable data.

## Alternatives Considered

- **Keep the lazy model and record failures in it.** It would also take the load errors out of every query. Not
  chosen: the database could still be held without a model, the optional field and its branch would stay, and no
  command has a path that does not need the model.
- **Record the raised error itself in the model.** Fewer types, since each error variant already holds its facts.
  Not chosen: an error holds the foreign exception it wraps and a traceback, so it is not persistable data, and it
  compares by identity. A governance that held one would never be recomputed equal, which breaks early cutoff.
- **A base class or a wrapping error for the load failures**, so that `Raises:` names one type. Not chosen: a base
  class is forbidden by [error-types](../code/error-types.md), and a wrapper only renames the failure. Neither makes
  the failing state unrepresentable.
- **The database decides skip or partial.** One policy in one place. Not chosen: the two consumers need different
  answers from the same revision, and a policy inside the database would make the model's facts depend on who asks.

## Deferred

| Deferred | What the design keeps open |
|---|---|
| The partial policy | An entry point of its own in the engine reads the same governance and judges the layers that loaded (prd-014 FR-012); nothing below it, and nothing it shares with the check run, changes |
| The last good meta spec | `advance` may keep the previous revision's loaded structure beside a new failure in the same layer, and a result checked against it is labelled so (prd-014 FR-013) |
| `advance(snapshot)` | Reserved, not built: it would carry the model over or load it again by its carry-over rule, and is the only other way to get a database |

## Checklist

Before committing code, verify:

- [ ] A database is obtained only from `Database.from_snapshot` or `advance`, and its model is never optional
- [ ] `model()`, `load_model` and every query raise no model-load error; a failure inside the declaration is a
  record in the model
- [ ] A load failure is recorded per meta spec layer, and listed once on the model with its path and condition
- [ ] A recorded failure is a frozen record of facts in a closed union, never an exception, and compares by value
- [ ] Each load failure is reported once, as an engine diagnostic at its own path, with a fixed error severity
- [ ] A documentation root or meta spec directory that cannot be listed is recorded like any load failure, and the
  check command, not the model, turns it into a failure that exits 2 before any subject is selected
- [ ] Neither the model nor the database decides skip or partial; the check run's entry point skips a document with a
  failed layer and lists it in coverage
- [ ] No code but the database builds a view over the snapshot; code below it reads only the view a query hands it
- [ ] Every value derived from the snapshot is a query on the database
- [ ] A per-document analysis reads the document's governance through `governance(ref)`, never the project model, and
  only the layers that loaded
- [ ] A source excerpt of a document, a `SKILL.md` or a resource is cut from its decode query's text, never decoded
  again
- [ ] Nothing patches a revision in place; work on an old revision is abandoned when a new one arrives
- [ ] No database's cache is filled from two threads at once
- [ ] An event changes an input and produces a new revision; it never updates a derived value directly

## References

- [prd-014-resilient-model-loading](prd-014-resilient-model-loading.md) - Source: The requirements this design answers
- [adr-004-database](adr-004-database.md) - Supersedes: The database this record restates
- [adr-001-snapshot-model](adr-001-snapshot-model.md) - Related: The model and the package roles
- [adr-002-vfs](adr-002-vfs.md) - Related: The snapshot the database wraps
- [adr-005-incremental](adr-005-incremental.md) - Related: What a query's result, and a recorded failure, carries over
- [adr-016-specifications](adr-016-specifications.md) - Related: The layers a failure is recorded per, and a meta
  spec that cannot be loaded as a failed layer
- [adr-006-specifications](adr-006-specifications.md) - Related: The record adr-016 supersedes
- [adr-009-rules](adr-009-rules.md) - Related: The engine conditions a load failure is reported as
- [adr-010-diagnostics](adr-010-diagnostics.md) - Related: The order, the report and the exit codes
- [adr-011-rules-engine](adr-011-rules-engine.md) - Related: The runner that applies the skip policy
- [adr-012-database-derivation](adr-012-database-derivation.md) - Related: The package the database lives in
- [error-types](../code/error-types.md) - Foundation: Why load failures are not grouped under a base class
- [pattern-memoization](../code/pattern-memoization.md) - Foundation: How a query is memoized
- [adr-023](adr-023-governed-items.md) - Related: Proposed replacement of per-kind decode, analysis and link-target
  query families with one governed-item query family
