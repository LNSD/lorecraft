---
name: "adr-001-snapshot-model"
description: "The snapshot model every package fits into: revisions of the workspace, each a set of inputs and the database of queries over them, the six package roles, and the symlink and Markdown link vocabulary. Load when adding a package, deciding which package code belongs in, or reviewing whether a change fits the snapshot model"
type: "adr"
status: "accepted"
---

# The Snapshot Model

> [!NOTE]
> Superseded in part by [adr-012-database-derivation](adr-012-database-derivation.md): the Derivation and
> Analysis rows of the role table below. The rest of this record binds code.

## Context

Lorecraft analyses the workspace one **revision** at a time: one set of inputs and the database built from
them. The **inputs** are what a revision is computed from: the snapshot, the disk read once into a value, and the
declarations. Other inputs may join them, such as the unsaved text of an open document or what an agent's command
line reports, each a value of its own. The **database** wraps the inputs, and everything derived from them is a
**query** on it: computed on first use, memoized for as long as the database lives, and read by every check and
every command through the database alone. A check is a pure function of what the queries return. The next
revision has new inputs and a new database, which may keep every query result the change between the two left
valid. A change that breaks this shape can leave every finding right and still make that carry-over unsound, so a
review holds it to the accepted ADRs in `docs/arch/` rather than to the tests.

Each layer of the model has a document of its own: the snapshot, the project model, the database, and incremental
computation across revisions. Two more cover how meta specs govern documents and what a check reports.

Two words are kept apart throughout: a **symlink** is a link in the filesystem, which the snapshot records and the
Input package follows, and a **Markdown link** is a link node in a document's parse tree.

## Decision

### Every Package Plays One Role

Each package under `src/lorecraft/` plays exactly one of six roles; one role may span several packages. The
layers contract in `pyproject.toml` fixes which package may import which. The role says what a package may do:

| Role | Does | Never |
|---|---|---|
| Base | Provides the generic infrastructure every package builds on: the project's standard library | Knows the domain, names a document or an agent, reads anything, or holds state |
| Declaration | States, as data, what Lorecraft reads and where: the layout, the scope, what each agent reads | Reads the disk or the environment to find out, or derives a value |
| Input | Reads the disk once, into a snapshot, and answers from it | Knows which directories matter, or what a file means |
| Derivation | Turns what a view holds into values: the model, a parse tree, a token count | Reads the disk, or caches a result across calls |
| Analysis | Holds the database of one revision, and the checks that judge its query results | Takes a snapshot, prints, or reads the workspace past the snapshot |
| Composition | Takes the snapshot, runs the analysis, writes the output | Holds a rule a check or a derivation should hold |

A package's own `module-*` document names its role. When code would make a package play a second role, it
belongs in the package that already plays that role.

## Consequences

- Whether a change fits the snapshot model is decided by review against these records, not argued case by case.
- Code that would give a package a second role moves to the package that already plays it, so the layers contract
  stays the whole story of what may import what.

## Checklist

Before committing code, verify:

- [ ] Every package plays the one role its `module-*` document names, and no change adds a second

## References

- [adr-002-vfs](adr-002-vfs.md) - Related: The snapshot, and the one boundary with the disk
- [adr-003-project-model](adr-003-project-model.md) - Related: The declared scope, apart from the captured content
- [adr-004-database](adr-004-database.md) - Related: Revisions, the view and the queries
- [adr-005-incremental](adr-005-incremental.md) - Related: Results carried over between revisions and processes
- [adr-006-specifications](adr-006-specifications.md) - Related: How meta specs govern documents
- [adr-007-findings](adr-007-findings.md) - Related: What a check reports, and how it reaches the user
- [adr-012-database-derivation](adr-012-database-derivation.md) - Superseded in part by: The Derivation and Analysis
  rows of the role table
- [principle-single-responsibility](../code/principle-single-responsibility.md) - Foundation: One role per package is
  one reason to change per package
