---
name: "module-lorecraft-project"
description: "The lorecraft.project package's responsibility, role, boundary and invariants: the project model, specifications and parse trees derived through a view, and the database of one revision that memoizes them. Load when adding or moving code in lorecraft.project, adding a specification dialect, a parse-tree node or a query, or deciding whether code derives a value or judges one"
type: "pkg"
scope: "pkg:lorecraft.project"
---

# The `lorecraft.project` Package

## Responsibility

Derive what a repository declares from a view of it. It changes when what a repository can declare, or what is
derived from it, changes: the specification dialect, the shape of a document and its parse tree, or a query.

## Role

**Derivation.** Every value here is a function of what a view holds, and the same view always gives the same
value. That is what lets the database here memoize it as a query for one revision, the only cache of values derived
from a snapshot, and one that never outlives its snapshot. The layout it derives against is a declaration, read from
`lorecraft.layout` and never stated here.

## Belongs Here

- The project model and the loader that builds it from listings and specifications.
- A repository that lists entries or reads text through a view, and decides what an entry is to Lorecraft.
- The decoding of a specification into rules that are proved usable when they are built.
- The parse tree, the token count and the line count: pure functions of one document's text.
- A shared analysis of one document's parsed values against the specifications handed to it, such as the problems
  each frontmatter schema finds, each placed on its field's line, or where the sections first stop matching an
  outline. It finds the facts several rules read; whether one is reported, and how, is a rule's.
- A document's, a skill's or a skill resource's identity, kept apart from its content and from where its symlinks
  lead.
- Turning a Markdown link's destination into a root-relative path, relative to the document that holds it.
- The contexts: a `Protocol` per subject kind stating what can be asked of one decoded document, skill or skill
  resource, the ones several kinds share, such as what any Markdown file has, and the owner types they return.
- The database of one revision: each query over it, such as the model, a file's decoded text, a parse tree, a count
  or a shared analysis, memoized on first use, and each question answered fresh from the snapshot, such as where a
  symlink leads.
- The witness a decode query returns, a file's ref and its decoded text, and the undecodable marker.
- The carry-over rule: which change to a revision's inputs invalidates which query; and what a persisted result is
  keyed by, and its validation before the database keeps it.
- A context implemented over the database: each fact of one decoded subject answered by its memoized query, each
  identity value read from the subject's ref or location.

## Belongs Elsewhere

| Code that… | Belongs in |
|---|---|
| Declares a fixed directory or suffix, or the scope a snapshot reads | `lorecraft.layout` |
| Reads the disk, or follows a symlink by asking the operating system | `lorecraft.vfs` |
| States an agent's skills directories or guide files | `lorecraft.agents` |
| Decides whether a document or a skill breaks a rule | `lorecraft.checks` |
| Runs the rules over the query results, or reports what they find | `lorecraft.checks` |
| Chooses which documents a run checks, or prints anything | `lorecraft.cli` |

## Invariants

- Every read goes through a view: the one a function is handed, or the one the database builds over its snapshot.
  Nothing here reads a workspace file, lists a directory or resolves a symlink by itself.
- The model holds structure and configuration: corpora, specifications, document and skill refs, and where each
  skill's symlinks lead. It never holds a document's content, and the loader never reads one.
- A parse tree, a token count and a line count read one document's text and nothing else, and return immutable
  values. No third-party parser type leaves the package.
- A shared analysis reads the parsed values and the specifications it is handed, never a view, and returns
  immutable values.
- Every memoized query reads one input: one file's bytes, or the structure. A shared analysis reads one file's
  per-file queries and the specifications the model says govern that file. A value drawn from several files is a
  query of its own, with its own carry-over rule, which its docstring states.
- A per-file query takes its decode query's witness, never a bare ref, is keyed by the ref, and carries over only
  when the next revision locates the ref at the same resolved file and its bytes are unchanged. Only the database
  builds a witness.
- Nothing derived from a snapshot is cached outside a database, or across revisions but by a carry-over rule. The
  database alone reads and writes the store of persisted results, through the store the Composition package hands it.
- A broken document is a value the parse returns, not an exception. A repository or specification error names
  its path and propagates.

## Examples

```python
# ❌ Bad — the loader reads each document's frontmatter to sort documents into the model: the model now
# changes whenever any document's text changes, so no change to a single file can leave it valid
def load_corpus(view: TreeView, corpus: CorpusId) -> Corpus:
    docs = [DocRef(path) for path in _markdown_files(view, corpus)]
    return Corpus(corpus, tuple(d for d in docs if _frontmatter(view.read_text(d.path)).get('type')))
```

```python
# ✅ Good — the model lists documents from the structure alone; what a frontmatter says is read per
# document, by the query that reads that document's bytes
def load_corpus(view: TreeView, corpus: CorpusId) -> Corpus:
    return Corpus(corpus, tuple(DocRef(path) for path in _markdown_files(view, corpus)))
```

## Checklist

Before committing code, verify:

- [ ] Every new read in `lorecraft.project` goes through a view
- [ ] A new query reads one input or states its own carry-over rule in its docstring, and takes a witness, not a
      bare ref, for a file's content
- [ ] Nothing added caches a value derived from a snapshot outside a database
- [ ] The model and its loader read no document's content
- [ ] A new parse or count reads one document's text, returns an immutable value, and leaks no parser type
- [ ] Nothing added declares a fixed directory, a suffix or the scope; the layout is read, never stated here
- [ ] Nothing added decides whether a document passes a rule

## References

- [adr-001-snapshot-model](../arch/adr-001-snapshot-model.md) - Foundation: The package roles
- [adr-012-database-derivation](../arch/adr-012-database-derivation.md) - Foundation: The Derivation role, the
  database included
- [adr-004-database](../arch/adr-004-database.md) - Foundation: Revisions, the view and the queries
- [adr-005-incremental](../arch/adr-005-incremental.md) - Foundation: The carry-over rule and persisted results
- [adr-003-project-model](../arch/adr-003-project-model.md) - Foundation: Declared scope against captured content, identity
  against location
- [adr-006-specifications](../arch/adr-006-specifications.md) - Foundation: Specifications decoded and proved usable at load
- [adr-002-vfs](../arch/adr-002-vfs.md) - Foundation: Every read of the workspace goes through the snapshot
- [adr-007-findings](../arch/adr-007-findings.md) - Foundation: A broken document is a finding, not a failure
- [principle-single-responsibility](principle-single-responsibility.md) - Foundation: One reason to change
- [pattern-repository](pattern-repository.md) - Foundation: Listing and reading through a view
- [pattern-memoization](pattern-memoization.md) - Foundation: How a query is memoized
