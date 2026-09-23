---
name: code-check
description: Lint Python code after changes. Use after editing .py files, when the user mentions lint errors, ruff warnings, import problems or code quality, or before commits and PRs. Auto-fixes the mechanical findings first, then surfaces the residue for hand-fixing.
compatibility: Requires the just task runner and uv. ruff is invoked through the project environment rather than a system install. Optionally uses JetBrains IDE diagnostics through the ide-index MCP server, which is not required.
allowed-tools: Bash(just check *) Bash(just check-fix *) mcp__ide-index__ide_diagnostics
---

# Code Checking Skill

Linting for this repository. Python has no compile step, so there is no `check` stage separate from
the linter: **ruff is the whole funnel**, and it runs over the entire repository in about a second.

That is the important difference from a compiled workspace. There is no per-package command to prefer
and no blast-radius escalation to reason about, because the cheap command is already the complete
one. Lint everything, every time.

## When to Use This Skill

Use this skill when you need to:
- Validate Python code after making changes
- Surface unused imports, undefined names, import-order problems, or bugbear findings
- Ensure code quality before a commit or PR

## Command Selection: Two Passes

```
Stage 0 (optional)              Stage 1 — mandatory
IDE diagnostics            →    just check-fix    →    just check
(mcp__ide-index__*)             (auto-apply)           (residue, hand-fix)
```

Run `check-fix` before `check`. Reversing them means reading a report of findings a tool was about to
fix for you.

## Stage 0 — IDE Diagnostics (Optional Fast Path)

If the session exposes the `ide-index` MCP server and the project is open in a JetBrains IDE,
`mcp__ide-index__ide_diagnostics` returns diagnostics already computed in the background, per file.
It catches things ruff does not — unresolved attributes, type mismatches the annotations imply.

Probe it once. If it errors or is unavailable, that is normal: skip to Stage 1 and do not treat the
absence as a failure. **Stage 0 is advisory and never terminal** — Stage 1 is mandatory regardless,
because the IDE index may be stale and ruff enforces rules the IDE does not know about.

## Available Commands

### Check with auto-fix
```bash
just check-fix [EXTRA_FLAGS]
```
Runs `ruff check . --fix`, rewriting every finding ruff can fix safely — unused imports, import
ordering, and similar. This is the **first** pass.

### Check without fixing
```bash
just check [EXTRA_FLAGS]
```
Runs `ruff check .`. This is the **residue** pass: whatever it reports after `--fix` needs a human
decision. It is also the gate the project treats as authoritative, so a clean result here is the
finish line.

Examples:
- `just check-fix` — standard first pass
- `just check` — residue pass, and the gate
- `just check --select UP` — preview a rule that is not in the select list, without enabling it
- `just check --statistics` — count the findings per rule while iterating

Both recipes accept extra flags, which are passed straight through to ruff.

### What is actually enabled

The select list is deliberately narrow: `E` (pycodestyle), `F` (pyflakes), `I` (isort ordering), and
`B` (bugbear). **There is no type checker in this repository** — no mypy, no pyright, no pre-commit
hook. An annotation is a claim nothing verifies, so a wrong one survives every gate here and must be
caught by review.

Several rule families are named as the designated enforcement for a rule in `docs/code/` but are
**not enabled** — `D` for docstrings, `TRY400` and `S110`/`S112` for error handling, among others.
Running `just check --select <rule>` to see what a family would report is useful; concluding from a
clean `just check` that those rules hold is not.

## Notes

### MANDATORY: Lint After Changes

Run this skill after code changes. Before a task is complete, `just check` must be clean.

A finding you cannot fix takes `# noqa: RULE — reason`, naming both. A bare `# noqa` hides which rule
was suppressed and why, and it silently keeps hiding the next rule that fires on that line.

### Example Workflow

1. Format first: `/code-format`.
2. **Stage 0** — probe `mcp__ide-index__ide_diagnostics` if available; fix what it reports in the
   files you edited.
3. **Stage 1** — `just check-fix`, then `just check`.
4. Hand-fix the residue. Re-run `just check` until clean.
5. Re-run `/code-format` if `--fix` rewrote source.
6. Done when `just check` reports `All checks passed!`.

## Common Mistakes to Avoid

### Anti-patterns
- **Never run `ruff check` directly** — use `just check`, which applies the project's env handling.
- **Never run the residue pass first** — `check-fix` before `check`.
- **Never silence a finding with a bare `# noqa`** — name the rule and the reason.
- **Never add a `# noqa` for a rule that is not in the select list** — it suppresses nothing and reads
  like enforcement that is not there. Delete it.
- **Never reorder imports by hand** — `--fix` owns import order, and a hand-sort is a diff ruff will
  redo.
- **Never conclude that a rule holds because `just check` is clean** — it only ran `E`, `F`, `I`, `B`.

### Best practices
- Format before linting, and again after `--fix` changes source.
- Fix findings rather than suppressing them; a suppression is a decision that needs a reason.
- Use `--select` to preview an unenabled rule family before proposing that it be turned on.
- Run the full pass when you finish a coherent chunk of work, and before committing.

## Pre-approved Commands

Safe to run without asking:
- `just check` — read-only.
- `just check-fix` — rewrites only files already in the working set, applying fixes ruff considers safe.
- `mcp__ide-index__ide_diagnostics` — read-only.

## Next Steps

After lint is clean:
1. **Run targeted tests** → use `/code-test`
2. **Check the changeset against the code rules** → use `/code-rules-check`
3. **Commit** → only once lint is green
