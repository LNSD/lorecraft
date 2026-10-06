---
name: docs-rules-creator
description: Write or change the Lorecraft specifications in docs/__meta__/ for any corpus under docs/ - a prose specification, and its structure specification for frontmatter schema, section outline, word caps and token budget. Use when adopting Lorecraft in a repository, adding a corpus or a namespace, adding a frontmatter field or a required section, changing a word cap or token budget, or fixing a specification that fails to load or that /docs-rules-check reported. Not for writing the documents a specification governs, see /docs-rules; not for reviewing a specification, see /docs-rules-check
compatibility: Requires the lorecraft command, on PATH or run through uvx lorecraft, or uv run lorecraft in a uv project that declares Lorecraft as a dependency
allowed-tools: Bash(lorecraft check*) Bash(lorecraft inspect*) Bash(uvx lorecraft *) Bash(uv run lorecraft *) Bash(grep *) Bash(ls docs/*)
---

# Docs Rules Creator

A specification is the set of rules for one group of documents under `docs/` — code rules, feature docs, or any
other corpus — kept in `docs/__meta__/` as a prose file and the machine-checkable file beside it. This skill is
the **writing path** for specifications: the files, their names, and the dialect the checks read.
`/docs-rules-check` is the review pass that validates the result.

The rules below are summaries. The authorities are Lorecraft's guides, and each section says which to read:
[spec](https://github.com/LNSD/lorecraft/blob/main/docs/feat/spec.md) for names and layering,
[spec-structure](https://github.com/LNSD/lorecraft/blob/main/docs/feat/spec-structure.md) for the structure file,
[spec-structure-frontmatter](https://github.com/LNSD/lorecraft/blob/main/docs/feat/spec-structure-frontmatter.md),
[spec-structure-outline](https://github.com/LNSD/lorecraft/blob/main/docs/feat/spec-structure-outline.md) and
[spec-structure-budget](https://github.com/LNSD/lorecraft/blob/main/docs/feat/spec-structure-budget.md) for its keys,
[workspace](https://github.com/LNSD/lorecraft/blob/main/docs/feat/workspace.md) for the layout.

## Running lorecraft

Every command below calls `lorecraft` directly. Where it is not on `PATH`, run `uvx lorecraft …` instead, or
`uv run lorecraft …` in a uv project that declares Lorecraft as a dependency. Run from the repository root.

## 1. The files and their names

```text
docs/__meta__/<name>.md               the prose: the authority, written for a reader
docs/__meta__/<name>.structure.json   the section rules, word caps, tokens budget and frontmatter
                                      schema, read by lorecraft check
```

What a file is comes from its **file type**, which a file name **pattern** claims: `*.md` claims the prose and
`*.structure.json` the structure specification. A file's extension is only what follows its last dot, and a
`<name>.<token>.json` that no pattern claims is not a specification file: it is left out, not read.

A **specification name**, the filename with its pattern's suffix stripped, is `<corpus>` or `<corpus>-<namespace>`.
The corpus names a directory `docs/<corpus>/` and never holds a hyphen, so the first hyphen ends it;
[spec](https://github.com/LNSD/lorecraft/blob/main/docs/feat/spec.md#filenames) and
[workspace](https://github.com/LNSD/lorecraft/blob/main/docs/feat/workspace.md#corpora) give the characters each part
may hold. The namespace names a group of documents in it: `code-python` governs `docs/code/python.md` and
`docs/code/python-*.md`. Nothing registers a file; its name is the whole binding. A directory under `docs/` becomes a
corpus the moment a file at its specification name exists.

**Layers only add.** A document answers to its corpus specification, then to every namespace specification
matching its name, broad to narrow, each applied on its own. So a namespace file states only what it adds, and
cannot relax what the corpus file says. A namespace file never governs alone: without a structure file at the
corpus specification name, every rule is unchecked for the whole corpus, and without the `frontmatter` key in it,
frontmatter is. A namespace `tokens` or outline still applies once that file exists.
[spec](https://github.com/LNSD/lorecraft/blob/main/docs/feat/spec.md#base-and-extension) has the rule.

**A base never names its extensions.** `code.md` does not mention `code-python.md` or its JSON, in its
references, its description, or inline; the extension names its base. Adding or removing a namespace then never
edits the corpus specification.

## 2. The prose comes first

**The prose is the authority, and the JSON is the same rules in a form a check applies.** Write or change the
prose, then the JSON to match, in the same change: nothing detects drift between them. A rule in prose that no
JSON file holds is unchecked; say in the prose which rules a reader must verify by hand.

A corpus specification that works with `/docs-rules` and `/docs-rules-check` covers, in order:

1. What the corpus holds — the kind of claim its documents make, so a writer can choose the corpus.
2. Frontmatter: each field, its vocabulary, and whether it is required.
3. Naming: what a filename says, and which prefixes group documents.
4. Cross-references: link form, and which direction links may point.
5. Document structure: the sections, their order, which are optional.
6. Content guidelines: what belongs in each section, and where overflow goes.
7. A template a writer can copy.
8. **A checklist** of `- [ ]` items, each verifiable by reading a document. `/docs-rules-check` walks it for
   everything the checks cannot decide, so a rule missing from it is not checked by anyone.

A namespace specification states only what it adds to its base, and links to it.

## 3. The frontmatter schema

The `frontmatter` key of `<name>.structure.json` is a JSON Schema, Draft 2020-12, for the parsed frontmatter mapping.
Its root states `"type": "object"` outright, and no schema in it carries `$id`; a `$schema` inside it, if any, names
Draft 2020-12. The corpus schema states the whole field set, with `required` and `"additionalProperties": false` so an
undeclared field is a finding. A namespace schema leaves both out and narrows a field the corpus allows. The schema
sees parsed YAML, so quoting is invisible to it; that `name` matches the filename is the check's own rule, not the
schema's. Copy the shapes in
[spec-structure-frontmatter](https://github.com/LNSD/lorecraft/blob/main/docs/feat/spec-structure-frontmatter.md).

## 4. The structure specification

`<name>.structure.json` states `empty_sections`, an `outline` of H2 sections — each `{"section": …}`, optionally
`"optional": true`, a `description` of what it holds and a non-empty list of `examples` of its body, each trimmed from
a real document of the corpus (the description and the first example are shown as notes when the section is missing),
or an `{"any": true}` run — with a `words` cap on any entry, `forbidden` sections, a whole-file `tokens` budget, and
the `frontmatter` schema of §3. Every key is optional, but a file states at least one rule. No key states that the
title is there: every governed document carries one H1 title that opens it, and `title` only caps its `words` or
`chars` or holds its text to a `pattern`. A namespace file usually wraps its additions in `any` runs so the corpus
outline still decides the rest.
[spec-structure-outline](https://github.com/LNSD/lorecraft/blob/main/docs/feat/spec-structure-outline.md) and
[spec-structure-budget](https://github.com/LNSD/lorecraft/blob/main/docs/feat/spec-structure-budget.md) have the keys,
examples, and what is refused on load;
[spec-structure](https://github.com/LNSD/lorecraft/blob/main/docs/feat/spec-structure.md) covers the file as a whole.

For editor validation, copy [the dialect's
schema](https://github.com/LNSD/lorecraft/blob/main/docs/schemas/structure.spec.json) to
`docs/schemas/structure.spec.json` and set `"$schema": "../schemas/structure.spec.json"` in each structure file.
`docs/schemas/` has no specification, so it is not a corpus.

Pick caps and a budget from the documents that exist: set them so today's good documents pass with room, and
say in the prose why each number is what it is. Never raise one to silence a finding; move or cut the content.

## 5. Recipes

**Adopt Lorecraft, or add a corpus.** Create `docs/<corpus>/`, then `docs/__meta__/<corpus>.md`, then
`<corpus>.structure.json` with a key for each rule you want checked. A rule without its key there is unchecked
for the whole corpus, unless a namespace file states it; the `frontmatter` key is unchecked without it there.
Write the first document only after the files exist, then follow `/docs-rules` for it. If the repository has an agent
guide, name the corpus there, and whether its documents are binding.

**Add a namespace.** Only when a group's documents genuinely share rules the rest of the corpus does not: a
prefix alone is not a reason. Create `<corpus>-<namespace>.md` and, when it adds a checkable rule, its structure file.

**Change a rule.** Edit the prose, then the JSON, then run the checks and fix what the change breaks in existing
documents in the same change, or say why they are left.

**Rename a group.** Rename the specification with the documents: a specification whose namespace matches nothing
still loads, and governs nothing.

## 6. Verify

```bash
lorecraft inspect   # loads every specification; exit 2 names a file that cannot be loaded
lorecraft check     # applies them to every document; exit 2 names a specification that cannot be loaded
```

Check in the tree that each document shows the specification names you meant, then run `/docs-rules-check` for
the review pass: prose against JSON, resolution, and the documents the change breaks.
