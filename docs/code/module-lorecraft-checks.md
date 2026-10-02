---
name: "module-lorecraft-checks"
description: "The lorecraft.checks package's responsibility, role, boundary and invariants: memoized per-revision queries, their carry-over rule, and checks as pure functions of what the queries return. Load when adding or moving code in lorecraft.checks, adding a check, a query or a cache, or deciding how a check gets its inputs"
type: "pkg"
scope: "pkg:lorecraft.checks"
---

# The `lorecraft.checks` Package

## Responsibility

Analyse one revision. It changes when what is derived from a revision's inputs, or the judgment made on it,
changes: a query, a check, or the shape of what a check reports.

## Role

**Analysis.** Two kinds of code share the role, and they stay distinct inside it. The database wraps one
revision's inputs and memoizes every derived value for as long as it lives. A check is a pure function of the values
those queries return. A run joins the two: it asks the queries for what a check reads, hands the check only that,
and locates each violation in its document.

## Belongs Here

- A query over one revision: the project model, the scope index, a skill's resource listing, a frontmatter node,
  a parse tree, a token count, memoized on first use.
- The carry-over rule: which change to a revision's inputs invalidates which query.
- What a persisted result is keyed by, and its validation against a new revision's inputs before the database
  keeps it.
- A question answered fresh from the snapshot or the declared scope, such as where a symlink leads.
- Resolving a Markdown link's target in the model: whether its path names a document, and the anchors it has.
- A check: values in, violations out.
- A run that resolves a check's inputs and turns violations into findings.
- The value types a check reports in, and their plain-text form.

## Belongs Elsewhere

| Code that… | Belongs in |
|---|---|
| Takes the snapshot, or chooses which documents or skills to check | `lorecraft.cli` |
| Prints, writes JSON, or sets an exit code | `lorecraft.cli` |
| Parses text, decodes a specification, or builds the model | `lorecraft.project` |
| Reads the disk | `lorecraft.vfs` |

## Invariants

- Every memoized query reads one input: one file's bytes, or the structure: listings, symlink targets, the declared
  scope and specifications. A value drawn from
  several files is a query of its own, with its own rule.
- A per-file query is keyed by an identity, a ref, and carries over only when the next model, or for a resource
  the next resource listing of its skill, locates the ref at the same canonical file and its bytes are unchanged.
- Each query's docstring states its carry-over rule: the changes that invalidate it. It is written or updated in
  the same change that adds or alters the query; the module docstring keeps only what holds for every query.
- A check takes the values it judges, its subject's identity values included, such as a filename, a corpus name
  or a skill's directory name, and performs no I/O. It never takes the database, a view or a path it could read
  through.
- A check returns violations that name no document. The run attaches the document.
- Check results are not cached. A check runs again every time.
- The database alone reads and writes the store of persisted results, through the store the Composition package
  hands it. A query or a check never sees the store.

## Examples

```python
# ❌ Bad — the check asks the database for itself: it can read any document, so nothing bounds what a
# change to one file invalidates, and a unit test needs a whole snapshot to test a rule about one heading
def validate_sections(db: AnalysisDb, ref: DocRef) -> tuple[Violation, ...]:
    return _outline_violations(db.parse(ref).headings, db.model().aspects_for(ref))
```

```python
# ✅ Good — the run resolves the inputs; the check is tested with a tuple literal
def validate_sections(aspects: tuple[OutlineRules, ...], *, headings: tuple[Heading, ...]) -> tuple[Violation, ...]:
    return _outline_violations(headings, aspects)
```

```python
# ❌ Bad — a run memoizes a value derived from the model and every skill's frontmatter on a module-level
# dict: it outlives the snapshot, and no carry-over rule names it
_NAMES_IN_USE: dict[str, SkillId] = {}
```

```python
# ✅ Good — the same value as a query on the database, declared with the change that invalidates it
def skill_names(self) -> Mapping[str, SkillId]:
    """Every skill's declared name; carried over only when no skill's frontmatter and no skills listing changed."""
```

## Checklist

Before committing code, verify:

- [ ] A new memoized query reads one input, or is declared with its own carry-over rule
- [ ] The query's docstring states its carry-over rule, updated in the same change as the query
- [ ] A per-file query is keyed by a ref, and its carry-over compares location and bytes, not bytes alone
- [ ] A new check takes values, identity values included, never the database, a view or a path it could read
      through, and performs no I/O
- [ ] A new check returns violations that name no document
- [ ] Nothing added takes a snapshot or sets an exit code

## References

- [arch-snapshot-model](arch-snapshot-model.md) - Foundation: The Analysis role
- [arch-database](arch-database.md) - Foundation: Revisions, the view and the queries
- [arch-incremental](arch-incremental.md) - Foundation: The carry-over rule and persisted results
- [arch-specifications](arch-specifications.md) - Foundation: A check applies the governing aspects it is handed
- [arch-findings](arch-findings.md) - Foundation: From violation to finding, and findings apart from failures
- [arch-project-model](arch-project-model.md) - Foundation: A per-file query keyed by identity, reading a location
- [principle-single-responsibility](principle-single-responsibility.md) - Foundation: One reason to change
- [pattern-memoization](pattern-memoization.md) - Foundation: How a query is memoized
