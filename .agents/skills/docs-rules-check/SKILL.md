---
name: docs-rules-check
description: Check a document under docs/ against the format specification that governs it in docs/__meta__/. Use when reviewing PRs, after editing anything under docs/, or before commits
compatibility: Requires uv to run the check commands and the script in scripts/
allowed-tools: Bash(uv run lorecraft check*), Bash(.agents/skills/docs-rules-check/scripts/check_budget.py*), Bash(git diff*), Bash(git status*), Bash(git merge-base*), Bash(grep *), Bash(ls docs/*), Bash(awk *)
---

# Doc Rules Check

Verifies that a document follows the specification in `docs/__meta__/` that governs it. This is a **format and
content-rules check, not a review**: it does not question whether the documented rule is the right rule, or
whether the code it describes works.

One question only: **does this document follow the specification that governs it?**

This skill carries no per-corpus rules. It resolves the specification from the document's own path and
validates against that document's checklist. `/docs-rules` is the writing path; invoke that one to author or
fix, this one to check.

## 1. The changeset

!`git diff --name-only HEAD -- 'docs/**/*.md'`

Uncommitted work is the default subject. For a whole branch use
`git diff --name-only $(git merge-base HEAD main)...HEAD -- 'docs/**/*.md'`; for a recent commit, `HEAD~1`.
Given explicit paths, check those instead.

Exclude `docs/__meta__/` itself: a specification is governed by its own corpus rules, not checked against them.

## 2. The specification that governs each one

!`grep -m 3 -E '^(description|type|scope):' docs/__meta__/*.md`

Resolve per document, from its path:

| Step | Rule |
|---|---|
| 1. Corpus | The first path segment under `docs/`. `docs/code/python-typing.md` is in the `code` corpus, however deeply nested. |
| 2. Specification | `docs/__meta__/<corpus>.md`. Read it; it is the authority for that corpus. |
| 3. Structure template | `docs/__meta__/<corpus>-<prefix>.md`, where `<prefix>` is the filename up to its first hyphen. Validate against it as well when the file exists. |

| Document | Corpus | Specification | Structure template |
|---|---|---|---|
| `docs/code/principle-least-surprise.md` | `code` | `docs/__meta__/code.md` | `docs/__meta__/code-principle.md` |
| `docs/code/pattern-registry.md` | `code` | `docs/__meta__/code.md` | `docs/__meta__/code-pattern.md` |
| `docs/code/python-typing.md` | `code` | `docs/__meta__/code.md` | `docs/__meta__/code-python.md` |
| `docs/code/test-functions.md` | `code` | `docs/__meta__/code.md` | none (`code-test.md` does not exist) |
| `docs/code/logging.md` | `code` | `docs/__meta__/code.md` | none |

`docs/code/` is the only corpus this repository carries today. A second one — feature docs under `docs/feat/`,
say — resolves by exactly the same rule, and until `docs/__meta__/feat.md` exists its documents are ungoverned.

Each specification is paired with three machine-checkable files at the same stem: `<stem>.header.json` holds
its frontmatter rules, `<stem>.structure.json` its section structure, `<stem>.budget.json` its length. The
commands in §3 and §4 and the script in §4 resolve and apply those; you read the prose.

Read the specification **before** the document, so the checklist is in hand while reading. Where step 2 finds
no specification, the document's format is ungoverned: report it as unvalidated rather than inventing rules or
borrowing another corpus's.

## 3. Frontmatter: run the command

**`lorecraft check header`** — validates the frontmatter of every Markdown file directly inside a corpus
under `docs/` against the JSON Schemas in `docs/__meta__/`; pass files to check only those. It decides every
frontmatter rule mechanically — required fields, vocabularies, naming patterns, the `Load when` trigger
clause, `name` against the filename — so do not check those by hand.

It finds the repository root by walking up to the nearest directory holding `docs/__meta__/`; `--root`
selects another. Document paths resolve from the working directory. Paths below are from the repository
root, which is where this repository's agents run:

```bash
uv run lorecraft check header                                          # every corpus
uv run lorecraft check header docs/code/python-typing.md               # named files
uv run lorecraft check header --root /path/to/repository --format json # machine-readable
uv run lorecraft check header --help                                   # flags and exit codes
```

Text findings print to stdout as `path:line: [rule] message`, each naming the schema behind it; the file count
goes to stderr. JSON output is one object with `checked`, `findings` and `ungoverned` keys. Exit 0 means no
findings, 1 means findings, 2 means bad usage or a specification in `docs/__meta__/` that cannot be loaded. A
`<corpus>.ungoverned` line means no schema governs that corpus — report it as unvalidated, not as a failure.

**`lorecraft check`**, with no check named, runs every check the command line carries — the header and
structure checks today, and each one that migrates from `scripts/` as it lands — over every document, reading
the tree once. It takes `--root` and `--format` but no paths. Its text output is each check's lines in turn and
one summary on stderr; its JSON output is `{"checks": {<name>: <that check's report>}}`, and its exit codes are
the same. It is how `just check-docs` runs them.

Where `uv` is unavailable, extract the frontmatter with the Grep tool (pattern `^---\n[\s\S]*?\n---`,
`multiline: true`, `output_mode: content`) or `awk '/^---$/{p=!p; print; next} p' <path>`, and work the
specification's frontmatter section by hand.

## 4. Sections and budgets: run the command and the script

**`lorecraft check structure`** — validates section structure against the structure specs in `docs/__meta__/`,
resolved by the same naming convention (`<corpus>.structure.json`, narrowed by
`<corpus>-<prefix>.structure.json` where one exists). A structure spec is not JSON Schema: an outline is a
sequence, and a corpus states **one** section order, which the spec holds as an outline the command walks. So
the spec decides which sections a document must carry, which it forbids, what order they come in, and
whether any section was left empty:

```bash
uv run lorecraft check structure                            # every corpus
uv run lorecraft check structure docs/code/python-typing.md # named files
uv run lorecraft check structure --help                     # flags and exit codes
```

Headings come from a Markdown parse, so a `#` comment inside a fenced code block is not a heading, and a
heading quoted in a blockquote or nested in a list item does not section the document. Root discovery, output
and exit codes match §3.

**`scripts/check_budget.py`** — counts prose words per document and per H2 section against the budget spec
resolved the same way (`<corpus>.budget.json`, overlaid by `<corpus>-<prefix>.budget.json`). Fenced code and
table rows are not counted. A corpus with no budget file prints `corpus.unbudgeted` and is not checked:

```bash
.agents/skills/docs-rules-check/scripts/check_budget.py docs/code/python-typing.md # named files
.agents/skills/docs-rules-check/scripts/check_budget.py --help                     # flags and exit codes
```

A budget finding on a section the change added prose to blocks, like any other finding. A finding on a
section the change did not touch is pre-existing: report it as such and leave it to the document's owner.
The fix for an overage is to move or cut, never to compress; the corpus specification's content guidelines
say where each kind of overflow belongs.

`just check-docs` runs `lorecraft check` and the script over the whole corpus, which is what CI gates on. Use it to confirm the
repository is clean; use the per-file invocations above while working a changeset.

## 5. Body: walk the checklist

**Every specification ends with a `## Checklist`, and those items are the check surface** — the rules restated
as verifiable statements. Walk each item against the document, plus the structure template's own checklist
where one applies.

The two commands and the script have settled the frontmatter, the section structure and the length, so what
is left here is what needs judgment: whether a section says what the specification asks of it,
cross-reference direction, and whether a `description` is genuinely discovery-optimized rather than merely
well-formed.

Check only what the diff touches — an unchanged document that breaks a rule is not this changeset's finding.
The one exception is §6.

## 6. Hunt for inventories that will rot

A list of files inside a document is a second source of truth that nothing keeps honest: it goes wrong on the
next file that lands, and no check fails when it does. **Flag every one, whether or not the changeset
introduced it.**

Look for a table or bullet list whose entries are documents, a "see also" naming each sibling in a corpus, or
a count ("the four principle docs"). For each, report the derivation that should replace it — a link to the
corpus directory, the naming convention that resolves the path, or the frontmatter discovery command.

A document's `References` section is legitimate and is not a finding: it names the documents that document
depends on, not everything that exists.

Where a list survives for a stated reason, verify it against the directory before passing it:

```bash
ls docs/<corpus>/
```

A list already out of sync is a finding regardless of the reason it exists.

## 7. Report

Clean:

> Doc rules check clean. Applied: `docs/__meta__/code.md`, `docs/__meta__/code-python.md`.

Violations, per document, most severe first, one per line, with the fix:

> `docs/code/python-typing.md:3` — **code.md §2**: `description` ends with a period and has no `Load when`
> clause. Drop the period and name the trigger conditions.

- **Every finding cites the specification and section that states the rule.** A finding with no specification
  behind it is a style opinion — drop it.
- Quote the checklist item when the violation is not self-evident.
- For a document whose corpus has no specification, report it as **unvalidated** and name the file that would
  govern it.
- Report a rule that seems wrong or contradicts another specification as a finding against the
  *specifications*, not against the document.

Fixes belong to the writing path: hand them to `/docs-rules`.

## Common Issues

The specification defines the exact requirement in each case; these are the ones that recur. The checks in §3
and §4 catch everything down to the blank line; the rest need reading.

- Invalid or unparseable frontmatter YAML
- `name` not in kebab-case, or not matching the filename minus `.md`
- `description` missing its `Load when` trigger clause, or ending with a period
- `type` or `scope` outside the vocabulary its specification defines
- `type` and `scope` not paired — a package-scoped document whose `scope` is `global`, or the reverse
- A frontmatter value left unquoted where the specification requires double quotes
- A frontmatter field the specification does not define, or a required one absent

- Wrong section names, missing required sections, or an empty optional section
- Required sections out of the specified order, or the reference sections not last and adjacent
- A document nested in a subdirectory its corpus keeps flat
- A `/`-prefixed link, which resolves against the site root rather than the repository
- Relative links not adjusted for the document's directory depth
- Cross-references pointing in a direction the specification forbids
- A hand-maintained list of documents that a new file will silently invalidate

## Pre-approved Commands

These run without user permission:

- `uv run lorecraft check`, `uv run lorecraft check header` and `uv run lorecraft check structure` with any flags — read-only, no side effects
- `.agents/skills/docs-rules-check/scripts/check_budget.py` with any flags — read-only, no side effects
- `just check-docs`, which runs the three checks over the whole corpus
- Frontmatter extraction (Grep tool or the `awk` fallback) on any file under `docs/`
- `ls` on any directory under `docs/`, to check a list against what is actually there
- All `git diff`, `git log`, and `git status` read-only commands
- Reading any file under `docs/` or `.agents/skills/`

## Not This Skill

| Use | For |
|---|---|
| `/docs-rules` | loading the specification in order to *write* a document |
| `/code-rules-check` | checking *code* against `docs/code/` |
| `/skills-check` | checking a skill against the Agent Skills specification |
