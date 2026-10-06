---
name: "module-lorecraft-checks"
description: "The lorecraft.checks package's responsibility, role, boundary and invariants: checks as pure functions of what a revision's queries return, and the runs that hand them those values. Load when adding or moving code in lorecraft.checks, adding a check, or deciding how a check gets its values or a rule its subject's context"
type: "pkg"
scope: "pkg:lorecraft.checks"
---

# The `lorecraft.checks` Package

## Responsibility

Judge one revision. It changes when the judgment made on a revision's query results changes: a check, the run of
the rules, or the shape of what a check reports.

## Role

**Analysis.** A check is a pure function of the values the queries of the database in `lorecraft.project` return.
A run hands it those values: it asks the queries for what a check reads, hands the check only that, and locates each
violation in its document. It runs the rules of `lorecraft.rules`, the layer below, the same way: it hands each
rule the context of the subject it judges, whose every fact is a query, and the rules are declared there.

## Belongs Here

- Resolving a Markdown link's target in the model: whether its path names a document, and the anchors it has.
- A check: values in, violations out.
- A run that resolves a check's inputs and turns violations into findings.
- Running the rules over a subject, each through the subject's context: a rule over a document or over the
  frontmatter only when the document is governed for the facet the rule declares, each facet it is not governed for
  recorded as coverage, and a rule over a Markdown file over a document governed for its structure, a skill's
  `SKILL.md` and each resource handed over as a subject of its own.
- The rule table: the rules a run enables, each with the severity it reports at, partitioned by the subject kind
  each judges or the frontmatter both kinds share, and a document's rules also by the facet each declares.
- The value types a check reports in, and their plain-text form.

## Belongs Elsewhere

| Code that… | Belongs in |
|---|---|
| Takes the snapshot, or chooses which documents or skills to check | `lorecraft.cli` |
| Prints, writes JSON, or sets an exit code | `lorecraft.cli` |
| Declares a rule, its identity or its group, or the base a rule derives from | `lorecraft.rules` |
| Declares what a context of a subject holds | `lorecraft.project` |
| Adds a query, a decode witness, a carry-over rule, or a context implemented over the database | `lorecraft.project` |
| Parses text, decodes a specification, or builds the model | `lorecraft.project` |
| Reads the disk | `lorecraft.vfs` |

## Invariants

- Nothing here memoizes a value derived from the snapshot. A value worth keeping for the revision is a query of
  the database, in `lorecraft.project`.
- A run matches each file's decode once, and hands a check only values read from a witness's queries.
- A check takes the values it judges, its subject's identity values included, such as a filename, a corpus name
  or a skill's directory name, and performs no I/O. It never takes the database, a view or a path it could read
  through.
- A check returns violations that name no document. The run attaches the document.
- Check results are not cached. A check runs again every time, and never sees the store of persisted results.

## Examples

```python
# ❌ Bad — the check asks the database for itself: it can read any document, so nothing bounds what a
# change to one file invalidates, and a unit test needs a whole snapshot to test a rule about one heading
def validate_sections(db: AnalysisDb, source: DocumentText) -> tuple[Violation, ...]:
    return _outline_violations(db.parse(source).headings, db.model().specs_for(source.ref).structure_specs())
```

```python
# ✅ Good — the run resolves the inputs; the check is tested with a tuple literal
def validate_sections(
    structure_specs: tuple[OutlineRules, ...], *, headings: tuple[Heading, ...]
) -> tuple[Violation, ...]:
    return _outline_violations(headings, structure_specs)
```

```python
# ❌ Bad — a run memoizes a value derived from the model and every skill's frontmatter on a module-level
# dict: it outlives the snapshot, and no carry-over rule names it
_NAMES_IN_USE: dict[str, SkillId] = {}
```

```python
# ✅ Good — the same value as a query on the database in lorecraft.project, declared with the change that
# invalidates it
def skill_names(self) -> Mapping[str, SkillId]:
    """Every skill's declared name; carried over only when no skill's frontmatter and no skills listing changed."""
```

## Checklist

Before committing code, verify:

- [ ] Nothing added memoizes a value derived from the snapshot; such a value is a query in `lorecraft.project`
- [ ] A new check takes values, identity values included, never the database, a view or a path it could read
      through, and performs no I/O
- [ ] A new check returns violations that name no document
- [ ] Nothing added takes a snapshot or sets an exit code

## References

- [adr-001-snapshot-model](../arch/adr-001-snapshot-model.md) - Foundation: The package roles
- [adr-012-database-derivation](../arch/adr-012-database-derivation.md) - Foundation: The Analysis role, the database
  apart
- [adr-004-database](../arch/adr-004-database.md) - Foundation: One report reads one revision
- [adr-006-specifications](../arch/adr-006-specifications.md) - Foundation: A check applies the governing structure specifications it is handed
- [adr-007-findings](../arch/adr-007-findings.md) - Foundation: From violation to finding, and findings apart from failures
- [principle-single-responsibility](principle-single-responsibility.md) - Foundation: One reason to change
- [pattern-memoization](pattern-memoization.md) - Foundation: How a query is memoized
