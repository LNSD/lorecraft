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

**Composition.** A command establishes the workspace root, takes a snapshot, maps its arguments onto the model,
hands the selection to an analysis run, and writes what comes back. It is the only package that touches the
process: the arguments, the working directory, standard output and the exit code.

## Belongs Here

- Finding the workspace root, from an option or from the working directory.
- Taking each snapshot, and building the revision every check of a report reads.
- Choosing where the store of persisted results lives, and handing it to the database.
- Mapping a path argument onto a document or a skill of the model, and refusing one that does not map.
- Registering commands and checks so a new one is a new module.
- Rendering findings and the model as text or JSON, and choosing the exit code.
- Writing out a failure chain, and the version.

## Belongs Elsewhere

| Code that… | Belongs in |
|---|---|
| Decides whether a document or a skill breaks a rule | `lorecraft.checks` |
| Memoizes anything derived from the snapshot | `lorecraft.checks` |
| Parses a document, or decides which specification governs it | `lorecraft.project` |
| Reads a file or lists a directory under the workspace root | `lorecraft.vfs` |

## Invariants

- Each report a command writes describes one revision. A bare `lorecraft check` runs every check over that
  revision.
- The disk is asked only to establish the root, and where an argument leads above it. Below the root, an argument
  is followed through the snapshot.
- The root is the only `Path` a command keeps. Everything handed below it is root-relative.
- A command handler composes: it holds no rule a check or a derivation should hold.
- Rendering is a pure function of the values a run returns.
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
# and a rule enforced here is invisible to a bare `lorecraft check`
def check_one(root: Path, argument: Path) -> int:
    db = AnalysisDb(capture(root, SCAN_SCOPE))
    if not argument.read_text(encoding='utf-8').startswith('---'):
        return _refuse('no frontmatter')
    return _report(check_frontmatter(db, _select(db, argument)))
```

```python
# ✅ Good — the argument is mapped through the snapshot, and the frontmatter rule stays in the check, where a
# bare `lorecraft check` applies it too
def check_one(root: Path, argument: Path) -> int:
    db = AnalysisDb(capture(root, SCAN_SCOPE))
    return _report(check_frontmatter(db, _select(db, argument)))
```

## Checklist

Before committing code, verify:

- [ ] Every check behind one report reads one revision: one snapshot, one database
- [ ] The disk answers only where the root is and where an argument leads above it; below, the snapshot does
- [ ] Nothing below the root is handed down as a `Path`
- [ ] A new rule lives in a check, not in a command handler
- [ ] A new output format renders values a run returned, and reads nothing itself

## References

- [arch-snapshot-model](arch-snapshot-model.md) - Foundation: The Composition role
- [arch-database](arch-database.md) - Foundation: One report, one revision
- [arch-vfs](arch-vfs.md) - Foundation: The disk is read only to take the snapshot and find the root
- [arch-findings](arch-findings.md) - Foundation: Deterministic output and exit codes
- [principle-single-responsibility](principle-single-responsibility.md) - Foundation: One reason to change
- [pattern-registry](pattern-registry.md) - Foundation: A command joins by registering
