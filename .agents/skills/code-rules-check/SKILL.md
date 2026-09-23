---
name: code-rules-check
description: Check a changeset against the code rules in docs/code/. Use after implementing and before committing, or when asked whether code complies with the guidelines.
compatibility: Requires a git checkout and the rule corpus in docs/code/. Reads only — no task runner, interpreter, container or network access is involved.
allowed-tools: Bash(git diff *) Bash(git merge-base *) Bash(grep *) Read
---

# Code Rules Check

Verifies that a changeset follows `docs/code/`. This is a **compliance check, not a review**: it does not hunt
bugs, question the design, or assess security.

One question only: **does this code follow the rules that govern it?**

## 1. The changeset

!`git diff --stat HEAD 2>/dev/null | tail -25`

Uncommitted work is the default subject. For a whole branch use
`git diff $(git merge-base HEAD main)...HEAD`. Check only what the diff touches — an unchanged file that
breaks a rule is not this changeset's finding.

## 2. The rules that govern it

!`grep -m 3 -E '^(description|type|scope):' docs/code/*.md`

Select by what the diff **contains**, not by what the task was about:

| The diff contains | Match triggers from |
|---|---|
| a new or changed signature, annotation, default argument, or `typing` import | `python-typing`, `python-naming` |
| an exception class, a `raise`, an `except`, a `try` | `python-exceptions`, `python-errors-handling` |
| an `import`, an `__init__.py`, an `__all__`, a new module, a `# noqa` | `python-modules` |
| a `"""` docstring or a `>>>` example | `python-docstrings` |
| a `@dataclass`, a pydantic model, or a config record | `python-dataclasses` |
| a value object, a registry entry, a `connect`/`__enter__` | `pattern-*` |
| a test, a fixture, a `conftest.py`, or a pytest marker | `test-*` |
| a log line or a `print` | `logging` |

Read every match. The `principle-*` descriptions in the catalog already state their rules — design violations
against those are in scope without reading the documents.

## 3. The check

**Every document ends with a `## Checklist`, and those items are the check surface** — the rules restated as
verifiable statements. Walk each item against each changed hunk.

Do this inline when the selection is small. Most changesets are: one coherent piece of work touches a few rule
groups, and the governing documents are usually already in context from `/code-rules` at the start of the
task — reading them again in a subagent would cost more than checking here.

**Escalate to a fan-out when the selection exceeds roughly four rule groups**, or when the diff spans several
packages under `src/lorewright/`. Then spawn one agent per group, all in a single message, each given its
group's document paths, the diff command, the instruction to apply those documents' `## Checklist` items, and
the report format from §4. Collect and deduplicate — two groups may flag one line under different rules, which
is reported once citing both.

Escalate only when breadth demands it. A fan-out over a three-file diff spends more than it finds.

## 4. Report

Clean:

> Rules check clean. Applied: `python-typing`, `python-errors-handling`, `python-docstrings`.

Violations, most severe first, one per line, with the fix:

> `src/lorewright/<module>.py:118` — **python-errors-handling**: this `except Exception` neither
> logs nor re-raises, so a document that failed to parse is indistinguishable from one with no frontmatter.
> Log it, or raise a `FrontmatterError` from it.

- **Every finding cites the document that states the rule.** A finding with no document behind it is a style
  opinion — drop it.
- Quote the checklist item when the violation is not self-evident.
- Do not report what ruff already catches; `/code-check` owns import order, unused names, and line length.
- A rule document naming a ruff rule as its enforcement does **not** mean that rule is enabled. Check the
  select list in `pyproject.toml` before assuming the linter caught something.
- Report a rule that seems wrong or contradicts another document as a finding against the *documents*, not
  against the code.

## Not This Skill

| Use | For |
|---|---|
| `/code-rules` | loading rules in order to *write* code |
| `/code-check` | what ruff reports — import order, unused names, line length |
| `/code-test` | whether the code works |
| `/code-review` | bugs, security and design, beyond what a document states |
