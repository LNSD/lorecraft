---
name: "module-lorecraft-checks"
description: "The lorecraft.checks package's responsibility, role, boundary and invariants: the runner that hands each rule its subject's context, the rule table and the report of a run. Load when adding or moving code in lorecraft.checks, changing how the rules run over a subject, or deciding how a rule gets its subject's context"
type: "pkg"
scope: "pkg:lorecraft.checks"
---

# The `lorecraft.checks` Package

## Responsibility

Judge one revision. It changes when the judgment made on a revision's query results changes: the run of the rules,
the rule table, or the shape of what a run reports.

## Role

**Analysis.** A run judges each subject by the rules of `lorecraft.rules`, the layer below, where the rules are
declared. It hands each rule the context of the subject it judges, whose every fact is a query of the database in
`lorecraft.project`, so a rule is a pure function of what its context answers. It locates each occurrence a rule
returns at its subject, as a diagnostic.

## Belongs Here

- Running the rules over a subject, each through the subject's context: a rule over a document or over the
  frontmatter only when the document is governed for the facet the rule declares, each facet it is not governed for
  recorded as coverage, and a rule over a Markdown file over a document governed for its structure, a skill's
  `SKILL.md` and each resource handed over as a subject of its own.
- The rule table: the rules a run enables, each with the severity it reports at, partitioned by the subject kind
  each judges or the frontmatter both kinds share, and a document's rules also by the facet each declares.
- The one-run selection, by `ALL`, group, code prefix or code, the most specific deciding, which filters the rule
  table and never changes a level.
- The value types a run reports in: a diagnostic per occurrence, the order they print in, and a report per subject.

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
- A run matches each subject's decode once, and hands a rule only the context of a decoded subject, never the
  database, a view or a path it could read through.
- A rule returns occurrences that name no subject. The run attaches the subject's path, as a diagnostic.
- A run's results are not cached. Every rule runs again every time, and never sees the store of persisted results.

## Examples

```python
# ❌ Bad — the run hands a rule the database: the rule can read any document, so nothing bounds what a change
# to one file invalidates, and a unit test needs a whole snapshot to test a rule about one heading
for enabled in table.document_rules_governed_by(Facet.OUTLINE):
    for occurrence in enabled.rule.check_in(database, source):
        diagnostics.append(RuleDiagnostic(source.ref.path, occurrence, enabled.severity))
```

```python
# ✅ Good — the run hands a rule its subject's context; a unit test hands it a fake context over a literal
context = DatabaseDocumentContext(database, source, governance, corpus_structure)
for enabled in table.document_rules_governed_by(Facet.OUTLINE):
    for occurrence in enabled.rule.check(context):
        diagnostics.append(RuleDiagnostic(source.ref.path, occurrence, enabled.severity))
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
- [ ] A rule is handed its subject's context, never the database, a view or a path it could read through
- [ ] A run attaches the subject's path to each occurrence; an occurrence names no subject
- [ ] Nothing added takes a snapshot or sets an exit code

## References

- [adr-001-snapshot-model](../arch/adr-001-snapshot-model.md) - Foundation: The package roles
- [adr-012-database-derivation](../arch/adr-012-database-derivation.md) - Foundation: The Analysis role, the database
  apart
- [adr-004-database](../arch/adr-004-database.md) - Foundation: One report reads one revision
- [adr-006-specifications](../arch/adr-006-specifications.md) - Foundation: A rule applies the governing structure specifications its context hands it
- [adr-007-findings](../arch/adr-007-findings.md) - Foundation: Findings apart from failures
- [principle-single-responsibility](principle-single-responsibility.md) - Foundation: One reason to change
- [pattern-memoization](pattern-memoization.md) - Foundation: How a query is memoized
