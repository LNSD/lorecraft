---
name: "arch"
description: "Architecture documentation format specification: the corpus in docs/arch/, its shared document numbering, frontmatter and closing references. Load when creating or editing any document in docs/arch/, or choosing its number"
type: "meta"
scope: "global"
---

# Architecture Documentation Format

**Applies to every document in `docs/arch/`.** Its machine-checkable half is
[arch.structure.json](arch.structure.json). Each kind of document in the corpus has a namespace specification of
its own, named after the kind, which adds its sections and vocabulary on top of this one.

## 1. What the Corpus Holds

The corpus in `docs/arch/` holds the documents written **before and while** a feature is built: what it must do,
how it is built, and the decisions taken on the way. Each document is one kind, and its kind is the prefix of its
filename. What shipped is described in `docs/feat/`, and how the code is written in `docs/code/`; an architecture
document links to both and restates neither.

**What binds code is the document's kind and status.** A kind's namespace specification says whether its
accepted documents bind code; where they do, an accepted document is a rule like any in `docs/code/`, loaded by
its frontmatter trigger and checked by its checklist. Any other document records what was required or decided,
and binds nothing. Once a feature ships, its feature doc is the authority on its behaviour.

## 2. Naming

A document is named `<kind>-<NNN>-<slug>.md`:

- **`<kind>`** is the document's kind, in lowercase letters, and selects the namespace specification that
  governs it. A document whose kind no namespace specification names is governed by this specification alone.
- **`<NNN>`** is a three-digit, zero-padded number from **one sequence shared by every document in the corpus**,
  whatever its kind. A new document takes one higher than the highest number in `docs/arch/`, so no two documents
  share a number, even of different kinds, and a directory listing sorted by number is the order they were
  written. A number is never reused, not even a dropped or superseded document's.
- **`<slug>`** names the subject in a few kebab-case words, for a reader scanning the directory. The kind and the
  number alone identify a document, and `<kind>-<NNN>` is how other documents cite it.

Two branches can take the same number. The one that merges second renumbers its document before merging, and
updates every citation of it, so a number is fixed only once it is on the main branch.

## 3. Frontmatter

| Field | Value | Notes |
|---|---|---|
| `name` | `<kind>-<NNN>-<slug>` | Matches the filename minus `.md` |
| `description` | One sentence | What the document decides or requires |
| `type` | The kind | Equals the filename's `<kind>` prefix |
| `status` | A word | Its vocabulary is the namespace specification's |

Every field is required, and no other field is allowed. That `type` equals the filename's prefix is checked by
review, not by the schema.

## 4. Cross-References

Documents cite each other by relative link, `[adr-004](adr-004-database.md)`, and by `<kind>-<NNN>` in
prose. A link to the code rules or the feature docs is relative too: `../code/module-lorecraft-vfs.md`,
`../feat/cli-check.md`. Citations go both ways: a document that leads to another names it under References, and the
other names it back.

## 5. Document Structure

A document has one H1 title, first in the file, and no empty section. It closes with **References**, the
documents and issues it comes from and leads to. Every other section is the namespace specification's to state.

**No length limit.** No section has a word cap and no file has a token budget: an architecture document is as
long as its requirements or its decisions need, and it is read when the work it describes is done, not loaded on
every task.

## 6. Template

````markdown
---
name: "{{kind}}-{{NNN}}-{{slug}}"
description: "{{What the document decides or requires, in one sentence}}"
type: "{{kind}}"
status: "{{status}}"
---

# {{Title}}

{{The sections the kind's namespace specification states.}}

## References

- [#{{issue}}]({{issue-url}}) - Source: {{The issue the document comes from}}
- [{{kind}}-{{NNN}}]({{kind}}-{{NNN}}-{{slug}}.md) - Leads to: {{The document it leads to}}
````

## 7. Checklist

- [ ] The file is named `<kind>-<NNN>-<slug>.md`, and `name` matches it
- [ ] The number is the next free one in `docs/arch/`, and no other document of any kind, merged or dropped, has it
- [ ] `type` equals the filename's kind prefix
- [ ] The document closes with References, and every document it cites names it back
- [ ] A renumbered document has every citation of it updated
