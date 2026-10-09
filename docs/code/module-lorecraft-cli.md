---
name: "module-lorecraft-cli"
description: "The lorecraft.cli package's responsibility, role, boundary and invariants: one revision per report, arguments mapped through it, the output and exit codes, and no rule logic. Load when adding or moving code in lorecraft.cli, adding a command or an output format, or deciding where a command's logic belongs"
type: "pkg"
scope: "pkg:lorecraft.cli"
---

# The `lorecraft.cli` Package

## Responsibility

Compose the layers below into the `lorecraft` commands. It changes when a command, its arguments, its output or
its exit codes change.

## Role

**Composition.** A command establishes the workspace root, takes a snapshot, selects the subjects of the model,
hands the selection to an analysis run, and writes what comes back. It is the only package that touches the
process: the arguments, the working directory, standard output and the exit code.

## Belongs Here

- Finding the workspace root, from an option or from the working directory.
- Taking each snapshot, and building the revision every check of a report reads.
- Choosing where the store of persisted results lives, and handing it to the database.
- Selecting the subjects a run checks from the model, and building the rule table it runs.
- Parsing `--select` and `--ignore` against the registry into the selection the rule table is built from, and
  warning on stderr of what a selection cannot do.
- Registering commands so a new one is a new module.
- Rendering diagnostics and the model as text, short lines or compact JSON, and choosing the exit code.
- Rendering the rulebook: a rule's page from its docstring, for `lorecraft rule` and for the recipe that writes
  `docs/rulebook/`, and the listing of every rule.
- The output formats and the exit statuses every command shares, in `output.py`.
- Writing out a failure chain, and the version.

## Belongs Elsewhere

| Code that… | Belongs in |
|---|---|
| Decides whether a document or a skill breaks a rule | `lorecraft.rules`, run by `lorecraft.checks` |
| Memoizes anything derived from the snapshot | `lorecraft.project` |
| Parses a document, or decides which meta spec governs it | `lorecraft.project` |
| Reads a file or lists a directory under the workspace root | `lorecraft.vfs` |

## Invariants

- Each report a command writes describes one revision. `lorecraft check` runs every enabled rule over that
  revision.
- The disk is asked only to establish the root, and where an argument leads above it. Below the root, an argument
  is followed through the snapshot.
- The root is the only `Path` a command keeps. Everything handed below it is root-relative.
- A command handler composes: it holds no rule a check or a derivation should hold.
- Rendering is a pure function of the values a run returns.
- A command that can print JSON takes `--format`, typed as an `Enum` of `output.py` (`OutputFormat`, or
  `DiagnosticFormat` where there is a short form); Typer refuses a value outside the set, and no command compares a
  raw string. JSON is one compact document. A command that does not succeed exits with an `ExitStatus`,
  `FINDINGS` when it ran and found something and `FAILURE` when it could not run.
- Every failure that escapes the packages below is written out here, as a chain.

## Examples

```python
# ❌ Bad — two snapshots behind one report: a file saved between them is checked in one state by one check
# and in another by the next, and the combined report describes no state the tree was ever in
def check_all(root: Path) -> int:
    findings = check_frontmatter(AnalysisDb(capture(root, SCAN_SCOPE)))
    findings += check_outline(AnalysisDb(capture(root, SCAN_SCOPE)))
    return _report(findings)
```

```python
# ✅ Good — one revision, read by every check of the report
def check_all(root: Path) -> int:
    db = AnalysisDb(capture(root, SCAN_SCOPE))
    return _report(check_frontmatter(db) + check_outline(db))
```

```python
# ❌ Bad — the command re-reads the argument from disk after the snapshot: it sees text the checks never saw,
# and a rule enforced here is invisible to every other command
def check_one(root: Path, argument: Path) -> int:
    db = AnalysisDb(capture(root, SCAN_SCOPE))
    if not argument.read_text(encoding='utf-8').startswith('---'):
        return _refuse('no frontmatter')
    return _report(check_frontmatter(db, _select(db, argument)))
```

```python
# ✅ Good — the argument is mapped through the snapshot, and the frontmatter rule stays in the check, where
# every command that runs it applies it too
def check_one(root: Path, argument: Path) -> int:
    db = AnalysisDb(capture(root, SCAN_SCOPE))
    return _report(check_frontmatter(db, _select(db, argument)))
```

## Checklist

Before committing code, verify:

- [ ] Every check behind one report reads one revision: one snapshot, one database
- [ ] The disk answers only where the root is and where an argument leads above it; below, the snapshot does
- [ ] Nothing below the root is handed down as a `Path`
- [ ] A new rule lives in `lorecraft.rules`, not in a command handler
- [ ] A new output format renders values a run returned, and reads nothing itself
- [ ] A command's `--format` is an `Enum` from `output.py`, and its exit codes are `ExitStatus` members

## References

- [adr-001-snapshot-model](../arch/adr-001-snapshot-model.md) - Foundation: The Composition role
- [adr-004-database](../arch/adr-004-database.md) - Foundation: One report, one revision
- [adr-002-vfs](../arch/adr-002-vfs.md) - Foundation: The disk is read only to take the snapshot and find the root
- [adr-007-findings](../arch/adr-007-findings.md) - Foundation: Deterministic output and exit codes
- [principle-single-responsibility](principle-single-responsibility.md) - Foundation: One reason to change
- [pattern-registry](pattern-registry.md) - Foundation: A command joins by registering
