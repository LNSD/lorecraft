---
name: code-rules-check
description: Check a code changeset against the repository's code rules in docs/code/ - select the code rules the diff falls under and walk each one's checklist against the changed lines, citing the code rule behind every finding. Use after implementing and before committing, when reviewing a pull request for compliance with the repository's conventions, or when asked whether code follows the guidelines. A compliance check, not a bug or security review
compatibility: Reads files only. Requires a git checkout and the code rules kept as Markdown documents in docs/code/ with name and description frontmatter
allowed-tools: Bash(git diff *) Bash(git status *) Bash(git merge-base *) Bash(grep *) Bash(ls docs/*) Read
---

# Code Rules Check

Verifies that a changeset follows the code rules (also called code specs) in `docs/code/`. This is a **compliance check, not a
review**: it does not hunt bugs, question the design, or assess security.

One question only: **does this code follow the code rules that govern it?**

If `docs/code/` does not exist, say so and stop: the repository has no code rules to check against.

## 1. The changeset

```bash
git diff --stat HEAD                                  # uncommitted work, the default
git diff "$(git merge-base HEAD main)"...HEAD         # a whole branch
```

Given explicit paths or commits, check those instead. Check only what the diff touches: an unchanged line
that breaks a code rule is not this changeset's finding.

## 2. The code rules that govern it

```bash
grep -m 3 -E '^(description|type|scope):' docs/code/*.md
grep -m 4 -E '^(description|status):' docs/arch/adr-*.md   # where the repository keeps decision records
```

An architecture decision record in `docs/arch/` whose `status` is `accepted` governs code as a code rule
does, and its checklist is checked the same way; one in any other status does not bind code.

Select by what the diff **contains**, not by what the task was about. Walk the hunks and, for each construct
in them — a signature, an exception handler, an import, a docstring, a test, a log line — find the code rules
whose trigger clause names it. Prefer the most specific spec in a group, and one scoped to the changed
package or directory over a global one. Read every match. Principle specs, whose descriptions state their
principles, are in scope without being read in full.

## 3. The check

**Each code rule's checklist is the check surface** — its conventions restated as verifiable statements. Walk
every item against every changed hunk it applies to. Where a spec has no checklist, walk its conventions.

Do this inline when the selection is small, which it usually is: one piece of work touches a few groups of code rules,
and the specs are often already in context from `/code-rules`.

**Fan out only when the selection exceeds about four groups**, or the diff spans several packages, and
only if you can run subagents. Then give each agent one group's spec paths, the diff command, the
instruction to apply those specs' checklists, and the report format below. Deduplicate what comes back:
two groups flagging one line are reported once, citing both.

## 4. Report

Clean:

> Code rules check clean. Applied: `python-typing`, `error-handling`, `python-docstrings`.

Violations, most severe first, one per line, with the fix:

> `src/app/loader.py:118` — **error-handling**: this `except Exception` neither logs nor re-raises, so
> a failed parse is indistinguishable from an empty file. Log it, or raise a domain error from it.

- **Every finding cites the code rule that states the convention.** A finding with no code rule behind it is a
  style opinion — drop it.
- Quote the checklist item when the violation is not self-evident.
- Do not report what the repository's linter or formatter already enforces. A code rule naming a lint rule
  does not mean the lint rule is enabled: check the linter's configuration before assuming it caught something.
- A convention that seems wrong, or contradicts another code rule, is a finding against the code rules, not the code.
