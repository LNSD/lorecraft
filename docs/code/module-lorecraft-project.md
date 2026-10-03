---
name: "module-lorecraft-project"
description: "The lorecraft.project package's responsibility, role, boundary and invariants: the project model, specifications and parse trees derived through a view. Load when adding or moving code in lorecraft.project, adding a specification dialect or a parse-tree node, or deciding whether code derives a value or judges one"
type: "pkg"
scope: "pkg:lorecraft.project"
---

# The `lorecraft.project` Package

## Responsibility

Derive what a repository declares from a view of it. It changes when what a repository can declare changes: the
specification dialect, or the shape of a document and its parse tree.

## Role

**Derivation.** Every value here is a function of what a view holds, and the same view always gives the same
value. That is what lets a query above memoize it for a snapshot's lifetime. The layout it derives against is a
declaration, read from `lorecraft.layout` and never stated here.

## Belongs Here

- The project model and the loader that builds it from listings and specifications.
- A repository that lists entries or reads text through a view, and decides what an entry is to Lorecraft.
- The decoding of a specification into rules that are proved usable when they are built.
- The parse tree, the token count and the line count: pure functions of one document's text.
- A document's, a skill's or a skill resource's identity, kept apart from its content and from where its symlinks
  lead.
- Turning a Markdown link's destination into a root-relative path, relative to the document that holds it.

## Belongs Elsewhere

| Code that… | Belongs in |
|---|---|
| Declares a fixed directory or suffix, or the scope a snapshot reads | `lorecraft.layout` |
| Reads the disk, or follows a symlink by asking the operating system | `lorecraft.vfs` |
| States an agent's skills directories or guide files | `lorecraft.agents` |
| Keeps a derived value across calls for the snapshot's lifetime | `lorecraft.checks` |
| Decides whether a document or a skill breaks a rule | `lorecraft.checks` |
| Chooses which documents a run checks, or prints anything | `lorecraft.cli` |

## Invariants

- Every read goes through the view it is handed. Nothing here reads a workspace file, lists a directory or
  resolves a symlink by itself.
- The model holds structure and configuration: corpora, specifications, document and skill refs, and where each
  skill's symlinks lead. It never holds a document's content, and the loader never reads one.
- A parse tree, a token count and a line count read one document's text and nothing else, and return immutable
  values. No third-party parser type leaves the package.
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

- [ ] Every new read in `lorecraft.project` goes through the view it is handed
- [ ] The model and its loader read no document's content
- [ ] A new parse or count reads one document's text, returns an immutable value, and leaks no parser type
- [ ] Nothing added declares a fixed directory, a suffix or the scope; the layout is read, never stated here
- [ ] Nothing added decides whether a document passes a rule

## References

- [adr-001-snapshot-model](../arch/adr-001-snapshot-model.md) - Foundation: The Derivation role
- [adr-003-project-model](../arch/adr-003-project-model.md) - Foundation: Declared scope against captured content, identity
  against location
- [adr-006-specifications](../arch/adr-006-specifications.md) - Foundation: Specifications decoded and proved usable at load
- [adr-002-vfs](../arch/adr-002-vfs.md) - Foundation: Every read of the workspace goes through the snapshot
- [adr-007-findings](../arch/adr-007-findings.md) - Foundation: A broken document is a finding, not a failure
- [principle-single-responsibility](principle-single-responsibility.md) - Foundation: One reason to change
- [pattern-repository](pattern-repository.md) - Foundation: Listing and reading through a view
