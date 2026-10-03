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
and locates each violation in its document. It runs the rules of `lorecraft.rules`, the layer below, the same
way: it builds the input each rule reads from the queries, and the rules are declared there.

## Belongs Here

- A query over one revision: the project model, the scope index, a skill's resource listing, a file's decoded
  text, a frontmatter node, a parse tree, a token count, memoized on first use.
- The witness a decode query returns, a file's ref and its decoded text, and the undecodable marker.
- The carry-over rule: which change to a revision's inputs invalidates which query.
- What a persisted result is keyed by, and its validation against a new revision's inputs before the database
  keeps it.
- A question answered fresh from the snapshot or the declared scope, such as where a symlink leads.
- Resolving a Markdown link's target in the model: whether its path names a document, and the anchors it has.
- A check: values in, violations out.
- A run that resolves a check's inputs and turns violations into findings.
- Building the input a rule reads from the queries, and running the rules over a subject.
- The value types a check reports in, and their plain-text form.

## Belongs Elsewhere

| Code that… | Belongs in |
|---|---|
| Takes the snapshot, or chooses which documents or skills to check | `lorecraft.cli` |
| Prints, writes JSON, or sets an exit code | `lorecraft.cli` |
| Declares a rule, its identity or its group, or the input type a rule reads | `lorecraft.rules` |
| Parses text, decodes a specification, or builds the model | `lorecraft.project` |
| Reads the disk | `lorecraft.vfs` |

## Invariants

- Every memoized query reads one input: one file's bytes, or the structure: listings, symlink targets, the declared
  scope and specifications. A value drawn from
  several files is a query of its own, with its own rule.
- A per-file query is keyed by an identity, a ref, and carries over only when the next model, or for a resource
  the next resource listing of its skill, locates the ref at the same resolved file and its bytes are unchanged.
- A file's bytes become text in its decode query alone, which turns a decode failure into the undecodable marker.
  A query about a file's content takes the witness, never a bare ref, and raises no decode error. Only the
  database builds a witness.
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
def validate_sections(db: AnalysisDb, source: DocumentText) -> tuple[Violation, ...]:
    return _outline_violations(db.parse(source).headings, db.model().governance(source.ref).structure_specs())
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
# ✅ Good — the same value as a query on the database, declared with the change that invalidates it
def skill_names(self) -> Mapping[str, SkillId]:
    """Every skill's declared name; carried over only when no skill's frontmatter and no skills listing changed."""
```

## Checklist

Before committing code, verify:

- [ ] A new memoized query reads one input, or is declared with its own carry-over rule
- [ ] The query's docstring states its carry-over rule, updated in the same change as the query
- [ ] A per-file query is keyed by a ref, and its carry-over compares location and bytes, not bytes alone
- [ ] A query about a file's content takes its decode query's witness, never a bare ref
- [ ] A new check takes values, identity values included, never the database, a view or a path it could read
      through, and performs no I/O
- [ ] A new check returns violations that name no document
- [ ] Nothing added takes a snapshot or sets an exit code

## References

- [adr-001-snapshot-model](../arch/adr-001-snapshot-model.md) - Foundation: The Analysis role
- [adr-004-database](../arch/adr-004-database.md) - Foundation: Revisions, the view and the queries
- [adr-005-incremental](../arch/adr-005-incremental.md) - Foundation: The carry-over rule and persisted results
- [adr-006-specifications](../arch/adr-006-specifications.md) - Foundation: A check applies the governing structure specifications it is handed
- [adr-007-findings](../arch/adr-007-findings.md) - Foundation: From violation to finding, and findings apart from failures
- [adr-003-project-model](../arch/adr-003-project-model.md) - Foundation: A per-file query keyed by identity, reading a location
- [principle-single-responsibility](principle-single-responsibility.md) - Foundation: One reason to change
- [pattern-memoization](pattern-memoization.md) - Foundation: How a query is memoized
