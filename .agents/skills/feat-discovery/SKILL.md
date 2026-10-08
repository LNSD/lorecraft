---
name: feat-discovery
description: Load the feat specs (feature docs) from docs/feat/ that match the user's query, frontmatter first. Use when the user asks what a part of the toolkit is, how it works, or what the project can do, or before implementing against a feature that may already be documented.
compatibility: Requires the feat spec corpus in docs/feat/. Reads only - no task runner, interpreter, container or network access is involved.
allowed-tools: Bash(awk *) Read
---

# Feature Discovery

Lazy-loads this repository's feat specs from `docs/feat/` against a user query, by matching YAML
frontmatter before reading any spec in full.

## When to Use

- The user asks "what is X?", "how does X work?", or what the toolkit can do
- The user names a part of the toolkit - a check, a meta spec, a command - and wants the
  context behind it
- Before implementing a feature, to find out what already exists

Sibling skills: `/feat-status` for the maturity each spec declares, `/docs-rules-check` for whether a
document is well-formed, `/code-rules` for how to write the code.

## Prefetched Feature Catalog

The frontmatter of all feat specs (loaded at skill start):

!`awk '/^---$/{p=!p; print FILENAME": "$0; next} p{print FILENAME": "$0}' docs/feat/*.md 2>/dev/null`

> **Fallback**: if the block above appears as literal text (the runtime does not auto-execute dynamic
> context), run it yourself with the Bash tool before proceeding.

**An empty catalog is an answer, not a failure.** It means no feature has been written up in this
repository yet. Say the corpus is empty, answer from the code and from `AGENTS.md`, and do not rerun the
command or go hunting for the specs somewhere else.

## Workflow

1. **Match** the user's query against the prefetched catalog using the fields below.
2. **Load** matched specs with the Read tool: `docs/feat/<name>.md`.
3. **Follow cross-references** in each spec's "References" section and load those too when relevant.

## Query Matching

Compare query against frontmatter fields:

- `name` - exact or partial match (e.g. "budget-check", "spec-dialect")
- `description` - semantic match (e.g. "frontmatter" -> the frontmatter check, "too long" -> the length budget)
- `components` - the identifiers a spec lists for the parts of the toolkit it covers: a checker module,
  a command surface, a meta spec. The corpus meta spec, `docs/__meta__/feat.md`, fixes that
  vocabulary; match on the identifier itself rather than on its prefix.

Load multiple feat specs when:

- The query spans several features
- Features cross-reference each other (`References` section)
- The user is working where two of them meet - a check and the meta spec it enforces

## When NOT to Use

| The user asks | Use instead |
|---|---|
| about code patterns or standards | `/code-rules` |
| to run a command | the matching `/code-*` skill |
| whether a document is well-formed | `/docs-rules-check` |
| how mature a feature is | `/feat-status` |

Whether the code actually does what a feat spec says is no skill's job here: read the spec and the
code and compare them by hand.

Simple file edits that do not need feature context need no discovery at all.
