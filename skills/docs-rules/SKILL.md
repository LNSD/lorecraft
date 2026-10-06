---
name: docs-rules
description: Load the Lorecraft specifications that govern a document under docs/ before writing it - its frontmatter, section outline, word caps and token budget. Use before creating or editing a document under docs/, when choosing which corpus a document belongs in, or when fixing findings from lorecraft check or /docs-rules-check. Not for writing the specifications themselves; see /docs-rules-creator
compatibility: Requires the lorecraft command, on PATH or run through uvx lorecraft, or uv run lorecraft in a uv project that declares Lorecraft as a dependency
allowed-tools: Bash(lorecraft check*) Bash(lorecraft inspect*) Bash(uvx lorecraft *) Bash(uv run lorecraft *) Bash(grep *) Bash(ls docs/*)
---

# Docs Rules

A repository that uses Lorecraft keeps its documentation in `docs/`, one directory per corpus, and the
specifications for each corpus in `docs/__meta__/`. This skill is the **writing path**: it gets you to the
specifications that govern a document before you write a line, so the document is right when written rather
than corrected afterwards. `/docs-rules-check` is the reading path that validates the result.

This skill carries no rules of its own. The specifications in `docs/__meta__/` are the authority; this skill routes
you into them. How Lorecraft lays out a repository is in
[workspace](https://github.com/LNSD/lorecraft/blob/main/docs/feat/workspace.md), and how a document's path selects its
specifications is in [spec](https://github.com/LNSD/lorecraft/blob/main/docs/feat/spec.md). Read them when a document
is not where you expect it or not governed the way you expect.

## Running lorecraft

Every command below calls `lorecraft` directly. Where it is not on `PATH`, run `uvx lorecraft …` instead, or
`uv run lorecraft …` in a uv project that declares Lorecraft as a dependency. Run from the repository root.

## 1. Resolve the specifications

Do not resolve specifications by hand. `lorecraft inspect` resolves them with the same rules the checks apply:

```bash
lorecraft inspect                 # a tree: corpora, their specification names, each document with its own, then the skills
lorecraft inspect --format json   # the same model; each document's governed_by lists its files
```

In the tree, each document is followed by the names of the specifications governing it, broad to narrow:
`pattern-state.md [code, code-pattern]` answers to `docs/__meta__/code.md`, then `docs/__meta__/code-pattern.md`. The
file at the same specification name that the pattern `*.structure.json` claims, the structure specification, is the
machine-checkable half the checks run: the frontmatter under its `frontmatter` key, the sections, the word caps and
the token budget. [cli-inspect](https://github.com/LNSD/lorecraft/blob/main/docs/feat/cli-inspect.md) describes the
output. The tree ends with the agent skills and the agents that read them, which writing a document does not need.

A document not yet written is not listed: create the file, empty if need be, and run it again. A file that
exists but is not listed is outside every corpus, and a corpus with no specification for a check is
ungoverned for it. Say so rather than inventing rules or borrowing another corpus's.

## 2. Choose the corpus

The corpus is a decision about **what kind of claim the document makes**, not its subject. Each corpus
specification says what its corpus holds; read the opening of each before choosing:

```bash
ls docs/__meta__/*.md
grep -m 2 -E '^(name|description):' docs/__meta__/*.md   # where specifications carry frontmatter
```

If none fits, the document probably belongs outside every corpus, at the `docs/` root, where no check reads it.
If it needs a corpus that does not exist yet, that is a new specification: use `/docs-rules-creator` first.

## 3. Write

1. **Read every specification the document answers to, before drafting**, the corpus specification first and
   each namespace layer after it. Most end with a checklist; that is what the document will be checked
   against, so hold it while writing. Reading it afterwards means rewriting.
2. **Read a neighbour.** Open the closest existing document in the corpus. The specification states the rules;
   a neighbour shows the register and depth the corpus settled on.
3. **Write the frontmatter first.** Deciding it forces you to decide what the document is. The
   `frontmatter` key of each `<name>.structure.json` states the fields exactly, and `name`, where a schema governs, matches the
   filename without `.md`.
4. **Write the body** from the specification's template or outline, keeping its sections in order.
5. **Run the checks** on the files you wrote, the frontmatter as soon as it exists:

   ```bash
   lorecraft check frontmatter <files>
   lorecraft check structure <files>
   lorecraft check budget <files>
   ```

   A missing-section finding may carry `= help:` and `= note:` lines describing the section and showing an
   example; follow them.

   A section over its word cap or a document over its token budget is moved or cut, not compressed: the
   specification's content guidelines say where each kind of overflow belongs.
6. **Run `lorecraft check`** with no paths before handing the change over. A new document can break a
   neighbour, and the per-file runs will not see that.
7. **Check the whole document** with `/docs-rules-check`, which covers what the checks cannot decide.

Work findings back through the specification rather than patching them one at a time. A finding usually
means a specification was not read, not that a line was mistyped.

## Traps

- **Optional sections are omitted, not left empty.** Most specifications forbid an empty section.
- **A trigger clause has two halves where the spec asks for one.** A `description` says what the document
  covers, then when to read it. The first half alone makes it unfindable; the second alone unidentifiable.
- **Cross-references are relative links**: `logging.md`, `../feat/cli.md`, never `/docs/code/logging.md`,
  which resolves against a site root and breaks for a reader of the repository.
- **Every corpus is flat.** A document in a subdirectory of its corpus is skipped silently.

## Inventories rot; do not write them

**A document never enumerates the files around it.** A list of a corpus's members, a table of every
specification, a "see also" naming each sibling: each is a second source of truth that goes wrong on the
next file that lands, and no check fails when it does. Write the derivation instead:

| Instead of listing | Point at |
|---|---|
| The documents in a corpus | The corpus directory |
| The specifications governing a document | `lorecraft inspect` |
| Where a subject is covered | The one or two documents that cover it, in the references section |

A references section is the one legitimate listing: it names what the document depends on, not everything that
exists.
