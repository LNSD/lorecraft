---
name: code-rules
description: Load the repository's code rules that apply to the work at hand, from the rule documents in docs/code/, reading their frontmatter first and only the documents whose triggers match. Use before planning or writing code, or when asked about the repository's conventions, standards, or design principles. Not for checking finished code; see /code-rules-check
compatibility: Reads files only. Requires the code rules to be kept as Markdown documents in docs/code/ with name and description frontmatter
allowed-tools: Bash(grep *) Bash(ls docs/*)
---

# Code Rules

A repository that uses Lorecraft keeps the rules for how its code is written as a corpus of rule documents in
`docs/code/`, one rule or topic per document. This skill loads only their frontmatter, and you choose what to
read from it. Selecting well is the whole job: read what the task needs, nothing more.

If `docs/code/` does not exist, say so: the repository has no code rules to load. Its specification, if one
exists, is `docs/__meta__/code.md`; `/docs-rules-creator` sets one up.

## 1. The catalog

Run this first; it is the whole index:

```bash
grep -m 3 -E '^(description|type|scope):' docs/code/*.md
```

Each `description` says what its document covers and, where the corpus specification asks for one, a trigger
clause — `Load when …` or similar — naming the situations the document governs. Other fields, such as `type`
or `scope`, are whatever `docs/__meta__/code.md` defines; read its frontmatter section once if their meaning is
not obvious.

## 2. Selecting

Match the task against the trigger clauses, then:

- **Take the most specific match.** A filename prefix is a group: `python-*`, `test-*`. Read the member whose
  trigger fits — the document on docstrings for a docstring, the one on handling errors for an `except` — not
  the group's broadest document. Add a broader one only when the task turns on what it owns.
- **Expect two to four documents.** One is common. More than four means the task is unscoped, or you are
  matching topics instead of triggers.
- **Break ties by specificity**: a document scoped to the package or directory being changed over a global
  one, where the frontmatter says which is which.
- **Read nothing adjacent.** If no trigger matches, say so: a gap in the rules is worth reporting.

Read selections at `docs/code/<name>.md`. Do not re-read what is already in context.

## 3. Rules that apply to all design work

Some rules — design principles, usually a `principle-*` group — govern every change, so no task will match
their triggers. Treat their catalog `description`s as the rules themselves and design against every one. Read
a full principle document only to argue one: to justify a decision, settle a disagreement, or cite it in a
review. Asked for the principles, read them all and summarise.

## 4. Applying

The rules are the repository's decisions, and they outrank general practice and your defaults. Where a rule
seems wrong for the task, follow it and raise the conflict; do not silently deviate. Each rule document usually
ends with a checklist: hold it while writing, since `/code-rules-check` checks the result against it.
