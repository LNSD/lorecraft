---
name: docs-rules-check
description: Review documents under docs/ and the Lorecraft meta specs in docs/__meta__/ that govern them - run lorecraft check for frontmatter, section outline, word caps and token budget, walk each meta spec's checklist for what a machine cannot decide, and check that each changed meta spec loads, that its prose and JSON agree, and that it governs the documents intended. Use after editing anything under docs/, when reviewing a pull request that touches docs/, before committing, when lorecraft check exits 2 or a document is unexpectedly ungoverned, or when setting the checks up in CI. Not for writing documents or meta specs; see /docs-rules and /docs-rules-creator
compatibility: Requires the lorecraft command, on PATH or run through uvx lorecraft, or uv run lorecraft in a uv project that declares Lorecraft as a dependency, and a git checkout
allowed-tools: Bash(lorecraft check*) Bash(lorecraft inspect*) Bash(uvx lorecraft *) Bash(uv run lorecraft *) Bash(git diff *) Bash(git status *) Bash(git merge-base *) Bash(grep *) Bash(ls docs/*)
---

# Docs Rules Check

The review pass over `docs/`. For a changed document it verifies that the document follows the meta specs
in `docs/__meta__/` that govern it; for a changed meta spec, that it loads, agrees with itself, and governs
what it claims to. This is a **conformance check, not a review of content**: it does not question whether a
convention is the right one, or whether the code a document describes works.

This skill carries no per-corpus conventions. It resolves the meta specs from each document's path and validates
against them. It reports; the fixes belong to the writing paths — `/docs-rules` for a document,
`/docs-rules-creator` for a meta spec.

## Running lorecraft

Every command below calls `lorecraft` directly. Where it is not on `PATH`, run `uvx lorecraft …` instead, or
`uv run lorecraft …` in a uv project that declares Lorecraft as a dependency. Run from the repository root.

## 1. The changeset

```bash
git status --short -- docs                                     # uncommitted work, the default
git diff --name-only "$(git merge-base HEAD main)"...HEAD -- docs   # a whole branch
```

Given explicit paths, check those instead. Split what changed in two:

- **Documents** — every changed Markdown file outside `docs/__meta__/`. §2 to §5 check them.
- **Meta specs** — every changed file in `docs/__meta__/`. A change to any file at a meta spec name is
  a change to that meta spec: its prose and every JSON file beside it. §6 checks them.

## 2. The meta specs that govern each document

```bash
lorecraft inspect
```

Each document is followed by the names of the meta specs governing it, broad to narrow; the name `<name>` is the
prose at `docs/__meta__/<name>.md`.
[cli-inspect](https://github.com/LNSD/lorecraft/blob/main/docs/feat/cli-inspect.md) describes the output. Read every
meta spec listed for a document **before** the document, so its checklist is in hand while reading. A document can
be governed for one part and not another;
[check](https://github.com/LNSD/lorecraft/blob/main/docs/feat/cli-check.md#key-concepts) says what governs each part.
Report a document as unvalidated for a part nothing governs, rather than borrowing another corpus's conventions.

## 3. Run the checks

The checks decide every mechanical requirement — required and allowed frontmatter fields, their vocabularies and
patterns, `name` against the filename, the title, section order, empty and forbidden sections, word caps and the
token budget. Do not check those by hand.

```bash
lorecraft check                              # every rule over every document and skill, one read of the tree
lorecraft check --format json                # machine-readable
lorecraft check --select OUT                 # one group's rules, by prefix, while fixing them; never the gate
```

The run covers the whole workspace; read the diagnostics for the documents the change touches. A diagnostic prints as
`path:line: severity[CODE]: message`, and may be followed by `-->`, `= help:` and `= note:` lines, or `labels` and
`children` in JSON; for a missing section they say what it holds and show a sample, so read them before fixing it.
Exit `0` means no error, warnings included, `1` at least one error, and `2` that the run could not happen: a
meta spec that cannot be loaded — §6 covers that one. A `<path>: ungoverned for <parts>` line on stderr is not a
failure; report the document as unvalidated for those parts. The rule groups and their codes, `FM` frontmatter, `OUT`
outline, `LEN` length, `LINK` links, are listed in
[check](https://github.com/LNSD/lorecraft/blob/main/docs/feat/cli-check.md#findings).

The run checks every agent skill too. A diagnostic at a skill's path, or a `LAY` one, is about a skill, not a
document, and falls outside this review.

A word cap or budget diagnostic on a section the change added to blocks, like any other error. One on a section
the change did not touch is pre-existing: report it as such. The fix for an overage is to move or cut, never to
compress.

## 4. Walk the checklist

**A meta spec's checklist is the check surface for what the commands cannot decide**: whether a section
says what the meta spec asks of it, cross-reference direction, whether a `description` genuinely helps a
reader find the document. Walk each item against each changed document, and each namespace layer's checklist
too. Where a meta spec has no checklist, walk its requirements instead.

Check only what the changeset touches — an unchanged document breaking a requirement is not this changeset's finding.
The one exception is §5.

## 5. Hunt for inventories that will rot

A list of files inside a document is a second source of truth nothing keeps honest. **Flag every one, whether
or not the changeset introduced it**: a table or list whose entries are documents, a "see also" naming each
sibling, a count ("the four principle documents"). For each, report the derivation that should replace it: the
corpus directory, a naming convention, or `lorecraft inspect`. A references section naming what a document
depends on is not a finding. Where a list survives for a stated reason, compare it with `ls docs/<corpus>/`; a
list already out of sync is a finding.

## 6. Changed meta specs

Lorecraft loads and validates each JSON file on its own, but it cannot tell whether the JSON says what the
prose says, or whether a meta spec name governs the documents its author meant. Check each changed
meta spec for both.

**Load.** `lorecraft inspect` validates every meta spec before any document is read. A structure file
must use only the dialect's keys and state usable values, and its `frontmatter` key must satisfy the JSON Schema Draft
2020-12 meta-schema, state `"type": "object"` at its root, and carry no `$id` at any depth. A leftover
`<name>.header.json` is not read: its schema belongs in that key now. A file that fails stops the run with an error
naming it: `inspect` and `lorecraft check` both exit `2`. That error is the finding;
[spec-structure](https://github.com/LNSD/lorecraft/blob/main/docs/feat/spec-structure.md) says what is refused for any
file, and [spec-structure-outline](https://github.com/LNSD/lorecraft/blob/main/docs/feat/spec-structure-outline.md),
[spec-structure-budget](https://github.com/LNSD/lorecraft/blob/main/docs/feat/spec-structure-budget.md) and
[spec-structure-frontmatter](https://github.com/LNSD/lorecraft/blob/main/docs/feat/spec-structure-frontmatter.md) what
is refused for their keys.

**Resolution.** In the `inspect` tree, compare what is governed with what was meant.
[spec](https://github.com/LNSD/lorecraft/blob/main/docs/feat/spec.md) states how a path selects its meta specs.

- Each changed meta spec appears under its corpus. A file whose name does not parse — a hyphen in a corpus name, a
  dot in a meta spec name, a `<name>.<token>.json` that no file type's pattern claims — is left out silently, and
  so is a namespace meta spec whose corpus has no file of its own or no directory under `docs/`.
- Each document lists the meta spec names intended. A namespace matches a filename that equals it or continues it
  with a hyphen: `code-python` governs `python-typing.md`, not `pythonic.md`.
- A namespace meta spec matches at least one document. One that matches none still loads and governs nothing,
  usually after a rename.
- For each part the corpus means to govern, the documents meant are governed, as
  [check](https://github.com/LNSD/lorecraft/blob/main/docs/feat/cli-check.md#key-concepts) defines it. A namespace
  file never governs alone: the checks read it only once the corpus meta spec has a structure file, and its
  `frontmatter` only once that file states the key.

**Agreement.** Nothing detects drift between a meta spec's prose and its JSON, so read both:

- Frontmatter: every frontmatter field the prose describes is in the `frontmatter` schema's `properties`, and
  none is only in the schema; required fields, vocabularies and patterns match the prose's wording.
- Structure: the prose's section list, order, and optional sections match `outline`; any word cap, token
  budget, forbidden section or empty-section requirement in one is in the other, with the same number.
- Layering: a namespace file states only what it adds, and does not restate or contradict its base. A
  namespace written as though it could relax a corpus requirement is a finding.
- Direction: the base names none of its extensions, in prose, `description`, or references.
- A checklist: the prose ends with checklist items for the requirements no JSON file holds, since those are checked by
  reading or not at all.

**Consequence.** Run `lorecraft check`. A meta spec change that breaks existing documents must fix them in the same
change, or say why they are left: a finding the changed meta spec introduced belongs to this changeset.

## 7. Report

Clean:

> Docs rules check clean. Applied: `docs/__meta__/code.md`, `docs/__meta__/code-python.md`.

Findings, per document or meta spec, most severe first, one per line, with the fix:

> `docs/code/python-typing.md:3` — **code.md, Frontmatter**: `description` has no trigger clause. Name the
> situations the document should be read in.
>
> `docs/__meta__/code.structure.json` — **drift**: its `frontmatter` schema allows `status`, which `code.md`'s
> frontmatter section does not describe. Describe it in the prose, or remove it from the schema.

- **Every document finding cites the meta spec and section that states the requirement.** A finding with no
  meta spec behind it is a style opinion — drop it.
- Quote the checklist item when the violation is not self-evident.
- A drift finding cites both halves; a load error is quoted as `lorecraft` printed it.
- A requirement that seems wrong, or contradicts another meta spec, is a finding against the meta spec.

## Setting the checks up in CI

`lorecraft check` is the whole gate: it runs every rule over every document and every skill, and exits
non-zero on an error or a meta spec that cannot load. Run it in CI and in a pre-commit
hook as is; do not narrow it to changed files, since a change to one document or meta spec can break
another.
