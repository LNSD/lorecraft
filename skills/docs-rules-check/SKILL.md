---
name: docs-rules-check
description: Review documents under docs/ and the Lorecraft specifications in docs/__meta__/ that govern them - run lorecraft check for frontmatter, section outline, word caps and token budget, walk each specification's checklist for what a machine cannot decide, and check that each changed specification loads, that its prose and JSON agree, and that it governs the documents intended. Use after editing anything under docs/, when reviewing a pull request that touches docs/, before committing, when lorecraft check exits 2 or a document is unexpectedly ungoverned, or when setting the checks up in CI. Not for writing documents or specifications; see /docs-rules and /docs-rules-creator
compatibility: Requires the lorecraft command, on PATH or run through uvx lorecraft, or uv run lorecraft in a uv project that declares Lorecraft as a dependency, and a git checkout
metadata:
  references: docs/feat/cli-check.md docs/feat/cli-check-frontmatter.md docs/feat/cli-check-structure.md docs/feat/cli-check-budget.md docs/feat/cli-inspect.md docs/feat/spec.md docs/feat/spec-structure.md docs/feat/spec-structure-budget.md docs/feat/spec-structure-frontmatter.md docs/feat/spec-structure-outline.md
allowed-tools: Bash(lorecraft check*) Bash(lorecraft inspect*) Bash(uvx lorecraft *) Bash(uv run lorecraft *) Bash(git diff *) Bash(git status *) Bash(git merge-base *) Bash(grep *) Bash(ls docs/*)
---

# Docs Rules Check

The review pass over `docs/`. For a changed document it verifies that the document follows the specifications
in `docs/__meta__/` that govern it; for a changed specification, that it loads, agrees with itself, and governs
what it claims to. This is a **rules check, not a review of content**: it does not question whether a rule is
the right rule, or whether the code a document describes works.

This skill carries no per-corpus rules. It resolves the specifications from each document's path and validates
against them. It reports; the fixes belong to the writing paths — `/docs-rules` for a document,
`/docs-rules-creator` for a specification.

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
- **Specifications** — every changed file in `docs/__meta__/`. A change to any file at a stem is a change to
  that stem: its prose and every JSON file beside it. §6 checks them.

## 2. The specifications that govern each document

```bash
lorecraft inspect
```

Each document is followed by the stems governing it, broad to narrow; stem `<stem>` is the prose at
`docs/__meta__/<stem>.md`. [cli-inspect](references/cli-inspect.md) describes the output. Read every
specification listed for a document **before** the document, so its checklist is in hand while reading. A
document with no stem stating what a check reads is ungoverned for that check: report it as unvalidated rather than borrowing
another corpus's rules.

## 3. Run the checks

The checks decide every mechanical rule — required and allowed frontmatter fields, their vocabularies and
patterns, `name` against the filename, the title, section order, empty and forbidden sections, word caps and the
token budget. Do not check those by hand.

```bash
lorecraft check                              # every check over every document, one read of the tree
lorecraft check frontmatter <files>          # frontmatter, the structure spec's frontmatter key
lorecraft check structure <files>            # sections and word caps, against <stem>.structure.json
lorecraft check budget <files>               # the whole-file token budget, the structure spec's tokens key
lorecraft check --format json                # machine-readable
```

Findings print as `path:line: [rule] message`, and may be followed by `= help:` and `= note:` lines, or a
`notes` list in JSON; for a missing section they say what it holds and show a sample, so read them before
fixing it. Exit `0` means no findings, `1` findings, and `2` that the run
could not happen: a rejected path, or a specification that cannot be loaded — §6 covers that one. A
`<corpus>.ungoverned` line is not a failure; report the corpus as unvalidated for that check. Each check's rule
identifiers are explained in its guide: [check](references/cli-check.md),
[frontmatter](references/cli-check-frontmatter.md), [structure](references/cli-check-structure.md),
[budget](references/cli-check-budget.md).

A word cap or budget finding on a section the change added to blocks, like any other finding. One on a section
the change did not touch is pre-existing: report it as such. The fix for an overage is to move or cut, never to
compress.

## 4. Walk the checklist

**A specification's checklist is the check surface for what the commands cannot decide**: whether a section
says what the specification asks of it, cross-reference direction, whether a `description` genuinely helps a
reader find the document. Walk each item against each changed document, and each namespace layer's checklist
too. Where a specification has no checklist, walk its rules instead.

Check only what the changeset touches — an unchanged document breaking a rule is not this changeset's finding.
The one exception is §5.

## 5. Hunt for inventories that will rot

A list of files inside a document is a second source of truth nothing keeps honest. **Flag every one, whether
or not the changeset introduced it**: a table or list whose entries are documents, a "see also" naming each
sibling, a count ("the four principle documents"). For each, report the derivation that should replace it: the
corpus directory, a naming convention, or `lorecraft inspect`. A references section naming what a document
depends on is not a finding. Where a list survives for a stated reason, compare it with `ls docs/<corpus>/`; a
list already out of sync is a finding.

## 6. Changed specifications

Lorecraft loads and validates each JSON file on its own, but it cannot tell whether the JSON says what the
prose says, or whether a stem governs the documents its author meant. Check each changed stem for both.

**Load.** `lorecraft inspect` validates every specification before any document is read. A structure
specification must use only the dialect's keys and state usable rules, and its `frontmatter` key must satisfy
the JSON Schema Draft 2020-12 meta-schema, state `"type": "object"` at its root, and carry no `$id` at any
depth. A leftover `<stem>.header.json` is not read: its schema belongs in that key now. A file that fails stops
the run with an error naming it: `inspect` exits `1`, `lorecraft check` exits `2`. That error is the finding; [spec-structure](references/spec-structure.md) says what is refused for any file, and
[spec-structure-outline](references/spec-structure-outline.md),
[spec-structure-budget](references/spec-structure-budget.md) and
[spec-structure-frontmatter](references/spec-structure-frontmatter.md) what is refused for their keys.

**Resolution.** In the `inspect` tree, compare what is governed with what was meant. [spec](references/spec.md)
owns the rules.

- Each changed stem appears under its corpus. A file whose name does not parse — a hyphen in a corpus name,
  a dot in a stem, an unknown aspect — is left out silently, and so is
  a namespace stem whose corpus has no file of its own or no directory under `docs/`.
- Each document lists the stems intended. A namespace matches a filename that equals it or continues it with a
  hyphen: `code-python` governs `python-typing.md`, not `pythonic.md`.
- A namespace stem matches at least one document. One that matches none still loads and governs nothing,
  usually after a rename.
- Every rule a corpus means to check has its key in the file at the corpus stem. A namespace file alone,
  or a namespace `frontmatter` key without a corpus one, leaves it unchecked.

**Agreement.** Nothing detects drift between a specification's prose and its JSON, so read both:

- Frontmatter: every frontmatter field the prose describes is in the `frontmatter` schema's `properties`, and
  none is only in the schema; required fields, vocabularies and patterns match the prose's wording.
- Structure: the prose's section list, order, and optional sections match `outline`; any word cap, token
  budget, forbidden section or empty-section rule in one is in the other, with the same number.
- Layering: a namespace file states only what it adds, and does not restate or contradict its base. A
  namespace written as though it could relax a corpus rule is a finding.
- Direction: the base names none of its extensions, in prose, `description`, or references.
- A checklist: the prose ends with checklist items for the rules no JSON file holds, since those are checked by
  reading or not at all.

**Consequence.** Run `lorecraft check`. A rule change that breaks existing documents must fix them in the same
change, or say why they are left: a finding the changed specification introduced belongs to this changeset.

## 7. Report

Clean:

> Docs rules check clean. Applied: `docs/__meta__/code.md`, `docs/__meta__/code-python.md`.

Findings, per document or stem, most severe first, one per line, with the fix:

> `docs/code/python-typing.md:3` — **code.md, Frontmatter**: `description` has no trigger clause. Name the
> situations the document should be read in.
>
> `docs/__meta__/code.structure.json` — **drift**: its `frontmatter` schema allows `status`, which `code.md`'s
> frontmatter section does not describe. Describe it in the prose, or remove it from the schema.

- **Every document finding cites the specification and section that states the rule.** A finding with no
  specification behind it is a style opinion — drop it.
- Quote the checklist item when the violation is not self-evident.
- A drift finding cites both halves; a load error is quoted as `lorecraft` printed it.
- A rule that seems wrong, or contradicts another specification, is a finding against the specification.

## Setting the checks up in CI

`lorecraft check` with no arguments is the whole gate: it runs every check over every document and exits
non-zero on a finding or a specification that cannot load. Run it in CI and in a pre-commit hook as is; do not
narrow it to changed files, since a change to one document or specification can break another.
