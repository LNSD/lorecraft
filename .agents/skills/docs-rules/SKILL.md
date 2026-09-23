---
name: docs-rules
description: Load the documentation rules that govern a document under docs/ - its format specification and content requirements. Use before creating or editing anything under docs/, when choosing which corpus a document belongs in, when adding a frontmatter field, or when fixing findings from /docs-rules-check
compatibility: Requires uv to run the checks in /docs-rules-check
allowed-tools: Bash(.agents/skills/docs-rules-check/scripts/check_header.py*), Bash(.agents/skills/docs-rules-check/scripts/check_structure.py*), Bash(.agents/skills/docs-rules-check/scripts/check_budget.py*), Bash(just check-docs*), Bash(grep *), Bash(ls docs/*), Bash(awk *)
---

# Doc Rules

`docs/__meta__/` holds the format specifications for `docs/`. This skill is the **writing path**: it gets you
to the right specification before you write a line, so the document is correct when written rather than
corrected afterwards. `/docs-rules-check` is the reading path that validates the result.

This skill carries no rules of its own. `docs/__meta__/` is the authority, and this skill routes you into it.

## Catalog

!`grep -m 3 -E '^(description|type|scope):' docs/__meta__/*.md`

> If the block above is literal text, the runtime did not execute it — run that grep yourself first.

## Resolving the Specification

A document's own path names its specification. No list of corpora is kept here, so a new corpus is covered as
soon as its specification exists.

For a document at `docs/<corpus>/…/<file>.md`:

| Step | Rule |
|---|---|
| 1. Corpus | The first path segment under `docs/`. `docs/code/python-typing.md` is in the `code` corpus, however deeply nested. |
| 2. Specification | `docs/__meta__/<corpus>.md`. It is the authority for that corpus. |
| 3. Structure template | `docs/__meta__/<corpus>-<prefix>.md`, where `<prefix>` is the filename up to its first hyphen. Write against it too, when it exists. |

| Document | Corpus | Specification | Structure template |
|---|---|---|---|
| `docs/feat/frontmatter-check.md` | `feat` | `docs/__meta__/feat.md` | none (`feat-frontmatter.md` does not exist) |
| `docs/code/principle-least-surprise.md` | `code` | `docs/__meta__/code.md` | `docs/__meta__/code-principle.md` |
| `docs/code/pattern-value-object.md` | `code` | `docs/__meta__/code.md` | `docs/__meta__/code-pattern.md` |
| `docs/code/python-typing.md` | `code` | `docs/__meta__/code.md` | `docs/__meta__/code-python.md` |
| `docs/code/logging.md` | `code` | `docs/__meta__/code.md` | none |

Each of those `.md` files is paired with machine-checkable files at the same stem:
`docs/__meta__/code.header.json` holds its frontmatter rules, `docs/__meta__/code.structure.json` its section
structure, `docs/__meta__/code.budget.json` its length budget. Read the `.md` for the prose; the JSON is the
exact field, section and word list, and it is what the checks run against.

Where step 2 finds no specification, the document's format is ungoverned. Say so rather than inventing rules
or borrowing another corpus's — never carry a rule from one corpus into another.

## Choosing the Corpus

The corpus is a decision about **what kind of claim the document makes**, not about its subject. A document
about frontmatter could land in several places depending on what it asserts.

| The document says | Corpus |
|---|---|
| How code in this repository is written | `docs/code/` |
| What behaviour this toolkit provides | `docs/feat/` |

If neither fits, the document probably does not belong in a governed corpus at all: operator and user guides
live at the `docs/` root, and agent workflow in `AGENTS.md` or a skill.

## Writing Path

1. **Resolve and read the specification.** Both the corpus specification and the structure template, **before
   drafting**. The corpus specification ends with a `Checklist`; that is what you will be checked against, so
   hold it while writing. Reading them afterwards means rewriting.
2. **Read a neighbor.** Open the closest existing document in the corpus and skim it. The specification states
   the rules; a neighbor shows the register and depth the corpus actually settled on. A document that
   satisfies the checklist but reads nothing like its neighbors is still wrong.
3. **Write the frontmatter first.** Not the body — deciding the frontmatter forces you to decide what the
   document is. The specification's Frontmatter Requirements section states the fields and their vocabularies,
   and its `.header.json` states them exactly; `name` always matches the filename minus `.md`.
4. **Write the body** from the specification's `Template` section, keeping its sections in the order given.
5. **Check the frontmatter** as soon as it is written, before the body is finished, then the sections once the
   body is drafted:

   ```bash
   .agents/skills/docs-rules-check/scripts/check_header.py <the files you wrote>
   .agents/skills/docs-rules-check/scripts/check_structure.py <the files you wrote>
   .agents/skills/docs-rules-check/scripts/check_budget.py <the files you wrote>
   ```

   The budget check counts prose words per document and per section against the corpus's
   `docs/__meta__/<corpus>.budget.json`. A section over budget is moved or cut, not compressed: the
   specification's content guidelines say where each kind of overflow belongs.

   `just check-docs` runs all three over the whole corpus. Run it before handing the change over — a new
   document can break a neighbor's cross-reference, and the per-file run will not see that.

6. **Check the whole document** with `/docs-rules-check`, which covers everything the scripts cannot decide.

Work findings back through this skill rather than patching them one at a time. A finding usually means a
specification was not read, not that a line was mistyped.

Four traps, each of which has bitten this repository:

- **`description` has two halves and needs both.** What the document covers, then a `Load when` clause naming
  the conditions to read it under. Third person, single line, no trailing period. The first half alone makes
  the document unfindable; the second alone makes it unidentifiable.
- **Optional sections are omitted, not left empty.** An empty section is a defect in every corpus.
- **Reference sections go last and stay adjacent.** `References` then `External References`.
- **Cross-references are relative links** — `python-exceptions.md`, `../feat/frontmatter-check.md`, never
  `/docs/code/python-exceptions.md`. A `/`-prefixed link resolves against the site root and breaks for every
  human reader. Label each with the target's `name` and the relationship the specification defines, and check
  the direction it allows.

## Inventories Rot; Do Not Write Them

**A document never enumerates the files around it.** A list of a corpus's members, a table naming every
specification, a "see also" naming each sibling — each is a second source of truth, and each is wrong from the
first file that lands after it. Nothing fails when one goes stale, so nobody notices until a reader trusts the
list and misses a document.

Every listing is derivable instead, and the derivation is what you write:

| Instead of listing | Point at |
|---|---|
| The documents in a corpus | The corpus directory, or the frontmatter discovery command |
| The specification governing a document | Its own path: `docs/__meta__/<corpus>.md` |
| The structure template for a document | Its filename prefix: `docs/__meta__/<corpus>-<prefix>.md` |
| Where a subject is covered | The one or two documents that actually cover it, in `References` |

A document's `References` section is the one legitimate listing: it names the handful of documents that
document depends on, not everything that exists.

When a document seems to need an inventory, it needs a link to the directory, a naming convention that
resolves the name, or a discovery command — never the list.

## Adding a Corpus

A new corpus is a new immediate subdirectory of `docs/` and needs these before its first document:

1. A specification at `docs/__meta__/<corpus>.md`, following the shape the existing ones share: core
   principles, frontmatter requirements, naming schema, cross-reference rules, document structure, content
   guidelines, template, checklist.
2. One `docs/__meta__/<corpus>.<aspect>.json` **for every aspect that already exists** in that directory,
   each holding the matching section of the new specification in the form its check reads. Copy the shape from
   another corpus's file for the same aspect; `ls docs/__meta__/*.json` says which aspects there are, and
   `/docs-rules-check` says which script reads each one. An aspect you skip is unchecked for the whole corpus.
3. A row in `AGENTS.md` under Canonical Resources, and a rank under Authority Order — a corpus that does not
   say whether it governs anything will be treated as though it does.
4. Structure templates at `docs/__meta__/<corpus>-<prefix>.md` for any filename prefix whose members need a
   fixed section set, each optionally paired with a `<corpus>-<prefix>.<aspect>.json` that narrows or replaces
   the corpus file for the documents carrying that prefix.

Nothing else registers the corpus: `just check-docs` walks all of `docs/`, so the new directory is picked up
as soon as its aspect files exist. Until they do, documents in the directory are ungoverned and
`/docs-rules-check` reports them as unvalidated, one aspect at a time.

**A rule lives in its aspect's file, or it does not exist.** When a corpus gains a frontmatter field or a
required section, add it to the specification and to the machine-checkable half in the same change: the
frontmatter schemas set `additionalProperties: false`, so an undeclared key is a finding, which is the point.

## Common Mistakes

| Mistake | Why it is wrong | Do this instead |
|---|---|---|
| Writing first, reading the specification after | Produces a rewrite, not a fix | Read both layers in step 1 |
| Borrowing a section list from another corpus | Corpora differ deliberately | Read the corpus's own template |
| A `description` with no `Load when` clause | The document cannot be lazily loaded | Write both halves |
| `name` not matching the filename | Breaks frontmatter discovery | Match it, minus `.md` |
| Inventing a frontmatter field | Splits the vocabulary silently | Amend the specification and its schema first |
| Leaving an optional section empty | An empty section is a defect | Omit it |
| Listing a corpus's documents in a document | The list rots on the next file that lands | Link the directory or give the discovery command |
| A rule document in a subdirectory | `docs/code/` is flat | Keep it at the corpus root |

## Pre-approved Commands

These run without user permission:

- `.agents/skills/docs-rules-check/scripts/check_header.py`, `check_structure.py`, and `check_budget.py` with any flags — read-only, no side effects
- `just check-docs`, which runs those three over the whole corpus
- Reading any file under `docs/` or `.agents/skills/`
- Frontmatter extraction: `awk '/^---$/{p=!p; print; next} p' <path>`
- `ls` on any directory under `docs/`

## Not This Skill

| Use | For |
|---|---|
| `/docs-rules-check` | validating what this skill writes |
| `/code-rules` | loading rules in order to write *code* |
| `/skills-check` | checking a skill under `.agents/skills/` against the Agent Skills specification |
