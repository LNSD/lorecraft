---
name: "module-lorecraft-project"
description: "The lorecraft.project package's responsibility, role, boundary and invariants: the project model, meta specs and parse trees derived through a view, and the database of one revision that memoizes them. Load when adding or moving code in lorecraft.project, adding a meta spec dialect, a parse-tree node or a query, or deciding whether code derives a value or judges one"
type: "pkg"
scope: "pkg:lorecraft.project"
---

# The `lorecraft.project` Package

## Responsibility

Derive what a repository declares from a view of it. It changes when what a repository can declare, or what is
derived from it, changes: the meta spec dialect, the shape of a document and its parse tree, or a query.

## Role

**Derivation.** Every value here is a function of what a view holds, and the same view always gives the same
value. That is what lets the database here memoize it as a query for one revision, the only cache of values derived
from a snapshot, and one that never outlives its snapshot. The layout it derives against is a declaration, stated
once in `lorecraft.project.layout` and read from there by every other module.

## Belongs Here

- The project model and the loader that builds it from listings and meta specs.
- A repository that lists entries or reads text through a view, and decides what an entry is to Lorecraft.
- The decoding of a meta spec into rules that are proved usable when they are built.
- The parse tree, token count and line count: pure functions of document text. The tree derives from the values
  `lorecraft.markdown` returns; `document` maps its line and link values into the project model and decodes raw
  frontmatter.
- A shared analysis of one document's parsed values against its meta specs: frontmatter violations mapped to
  project-owned problems and placed on field lines, or where sections first stop matching an outline. It finds
  facts several rules read; whether one is reported, and how, is a rule's.
- A document's, a skill's or a skill resource's identity, kept apart from its content and from where its symlinks
  lead.
- The common reference and model-resolved descriptor for corpus documents and skill entries, including their
  report path, read location, link base, origin metadata, governance target and active check facets.
- Turning a Markdown link's destination into a root-relative path, from its document's directory or its skill's
  root, and what the snapshot holds there.
- Contexts: protocols for decoded documents, skills, resources and layout entries, with shared questions and
  project-owned return types.
- The one-revision database: one memoized decode and per-file query family keyed
  by the common reference for documents and skill entries, other memoized derived queries, and fresh snapshot
  questions such as symlink targets.
- The witness a decode query returns: a file's ref and decoded text, or the undecodable marker with its first
  invalid byte's line, offset, bytes and reason.
- The carry-over rule: which change to a revision's inputs invalidates which query; and what a persisted result is
  keyed by, and its validation before the database keeps it.
- A context over the database: decoded facts answered by memoized queries, identity read from the subject's ref or
  location, and layout facts read from its record.

## Belongs Elsewhere

| Code that… | Belongs in |
|---|---|
| Reads the disk, or follows a symlink by asking the operating system | `lorecraft.vfs` |
| Scans, parses or refuses YAML text | `lorecraft.yaml` |
| Parses Markdown text, or reads a parser's nodes | `lorecraft.markdown` |
| Supplies JSON Schema vocabulary and library-independent validation facts | `lorecraft.jsonschema` |
| States an agent's skills directories or guide files | `lorecraft.agents` |
| Decides whether a document or a skill breaks a rule | `lorecraft.rules` |
| Runs the rules over the query results | `lorecraft.engine` |
| Declares what a run reports about what the rules find | `lorecraft.rules` |
| Chooses which documents a run checks, or prints anything | `lorecraft.cli` |

## Invariants

- Every read goes through a view: the one a function is handed, or the one the database builds over its snapshot.
  Nothing here reads a workspace file, lists a directory or resolves a symlink by itself.
- The model holds structure and configuration: corpora, meta specs, document and skill refs, common Markdown item
  descriptors, and where each skill's symlinks lead. It never holds a document's content, and the loader never
  reads one.
- A parse tree, a token count and a line count read one document's text and nothing else, and return immutable
  values. No third-party parser type leaves the package.
- A shared analysis reads the parsed values and the meta specs it is handed, never a view, and returns
  immutable values.
- A frontmatter schema maps owned JSON Schema violation facts to `FrontmatterProblem` values with project guidance; it
  never reads validator records.
- A memoized query is an input query or a derived one. An input query reads one input from the snapshot, one
  file's bytes or the structure, and states its carry-over rule. A derived query reads only other queries and
  hands them to one package function; its arguments are its read set, so it carries over when they do. A shared
  analysis reads one file's queries and its governing meta specs. A value drawn from several files is its own
  query, with its carry-over rule in its docstring.
- A per-file query takes its decode query's witness, never a bare ref, is keyed by the ref, and carries over only
  when the next revision locates the ref at the same file with unchanged bytes. Only the database builds a witness.
- Nothing derived from a snapshot is cached outside a database, or across revisions but by a carry-over rule. The
  database alone reads and writes the store of persisted results, through the store the Composition package hands it.
- A broken document is a value the parse returns, not an exception. A unit the loader cannot load is a recorded
  value, never raised.
- A refused `docs/` alias does not stop a skill resource walk.

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
- [ ] A new derived query reads no view, only other queries, and passes what it read to one function of the
      package
- [ ] Nothing added caches a value derived from a snapshot outside a database
- [ ] The model and its loader read no document's content
- [ ] A unit the loader cannot read or use is recorded as a frozen value of facts in a closed union, never raised
      and never held as an exception
- [ ] A new parse or count reads one document's text, returns an immutable value, and leaks no parser type
- [ ] Nothing added outside `lorecraft.project.layout` declares a fixed directory, a suffix or the scope; it
      reads them from there
- [ ] Nothing added decides whether a document passes a rule

## References

- [adr-001-snapshot-model](../arch/adr-001-snapshot-model.md) - Foundation: The package roles
- [adr-012-database-derivation](../arch/adr-012-database-derivation.md) - Foundation: The Derivation role, the
  database included
- [adr-015-database](../arch/adr-015-database.md) - Foundation: Revisions, the view and the queries
- [adr-005-incremental](../arch/adr-005-incremental.md) - Foundation: The carry-over rule and persisted results
- [adr-003-project-model](../arch/adr-003-project-model.md) - Foundation: Declared scope against captured content, identity
  against location
- [adr-016-specifications](../arch/adr-016-specifications.md) - Foundation: Meta specs decoded and proved usable at load
- [adr-002-vfs](../arch/adr-002-vfs.md) - Foundation: Every read of the workspace goes through the snapshot
- [adr-010-diagnostics](../arch/adr-010-diagnostics.md) - Foundation: A broken document is a diagnostic, not a failure
- [adr-017-yaml-parser](../arch/adr-017-yaml-parser.md) - Foundation: Frontmatter parsed with a pure-Python YAML parser
- [adr-019-frontmatter-format](../arch/adr-019-frontmatter-format.md) - Foundation: The frontmatter format, and how the rest is refused
- [principle-single-responsibility](principle-single-responsibility.md) - Foundation: One reason to change
- [pattern-repository](pattern-repository.md) - Foundation: Listing and reading through a view
- [pattern-memoization](pattern-memoization.md) - Foundation: How a query is memoized
