---
name: "module-lorecraft-engine"
description: "The lorecraft.engine package's responsibility, role, boundary and invariants: the shared runner that hands each rule the facts of its query, and each mode's own entry point. Load when adding or moving code in lorecraft.engine, changing how the rules run over a subject, adding a mode of the engine, or deciding how a rule gets its facts"
type: "pkg"
scope: "pkg:lorecraft.engine"
---

# The `lorecraft.engine` Package

## Responsibility

Run the rules over one revision's subjects, and report what failed to load. It changes when the way a subject is
judged changes, when check mode skips a subject whose docs target was refused, when a mode's policy for a document
governed by a failed layer changes, or when a load failure is reported differently.

## Role

**Analysis.** A run judges each subject by the rules of `lorecraft.rules`, the layer below, where the rules are
declared. It resolves the query each rule names against the subject it judges, a query of the database in
`lorecraft.project`, and hands the rule its facts, so a rule is a pure function of what its query answers. It locates each occurrence a rule
returns at its subject, as a diagnostic of `lorecraft.rules.report`.

## Belongs Here

- The shared runner (`runner.py`): the governance lookup, facet gating, running the table's rules over a
  subject through their queries, and building its report. A rule query is resolved for its subject, whether that
  subject is a Markdown item, symlink or corpus directory; each kind follows the same query and judgment path. A
  query is owned by its rule group unless another group needs it, when it is promoted to `lorecraft.project.query`;
  the runner resolves that shared query for both groups through the same database. A
  document, skill or skill resource is decoded by each mode's entry point, so its policy comes after decoding,
  and `judge_item` judges any of them through one facet loop
  over the descriptor's active facets. A rule runs over an item of a kind it applies to, and only when the item is governed
  for the facet the rule reads; each facet an applicable rule reads that the item is not governed for is recorded as
  coverage. A rule over a Markdown file runs over a document governed for its structure, a skill's `SKILL.md` and
  each resource handed over as a subject of its own. A resource has no corpus structure governance, while package
  Markdown checks still run; a skill's package checks run independently of corpus governance.
- One entry point per mode: `skip.py` gives documents governed by a failed layer no rule, and
  skips skill entrypoints whose docs target was refused. An LSP-style partial mode is future work.
- `skip.py` wraps an item read failure in the kind-specific error declared by the document or skill repository. A
  specification has no kind-specific read error, so its `ItemReadError` propagates unchanged.
- The report of each load failure the model lists (`load_failures.py`): the engine condition of its kind, filed
  once at the failure's path, whatever the configuration and the selection. A `docs/` or `docs/__meta__/` that
  cannot be listed comes back as `UnlistableRoot` instead of a report. Which failure stops a run is the command's
  choice, never the engine's.

## Belongs Elsewhere

| Code that… | Belongs in |
|---|---|
| Takes the snapshot, or chooses which documents or skills to check | `lorecraft.cli` |
| Prints, writes JSON, or sets an exit code | `lorecraft.cli` |
| Declares a rule, its identity or its group, or the base a rule derives from | `lorecraft.rules` |
| Builds the rule table, applies a level or a one-run selection, or declares what a run reports | `lorecraft.rules` |
| Adds a project query, a query promoted for cross-group reuse, a decode witness, or a carry-over rule | `lorecraft.project` |
| Parses text, decodes a meta spec, or builds the model | `lorecraft.project` |
| Reads the disk | `lorecraft.vfs` |

## Invariants

- Nothing here memoizes a value derived from the snapshot. A value worth keeping for the revision is a query of
  the database, in `lorecraft.project`.
- A run matches each subject's decode once, resolves each rule's query for that subject through the database, and
  hands the rule only those facts, never the database, primitives, a view or a path it could read through.
- Markdown items, symlinks and corpus directories use the same queried-rule dispatch; no layout subject is judged
  through a separate direct path.
- A rule returns occurrences that name no subject. The run attaches the subject's path, as a diagnostic.
- A load failure is reported once, at its own path, and never once per subject it touches; a document a failed layer
  governs is coverage, never a diagnostic. A skill still receives its Agent Skills checks.
- A skill entrypoint whose docs target was refused is coverage at its own path; the refusal is reported at the target.
- A run's results are not cached. Every rule runs again every time, and never sees the store of persisted results.
- The shared runner holds no mode's policy. A new mode is a new entry point that edits neither `runner.py` nor
  another mode's entry point.
- Nothing here imports `lorecraft.cli` or `typer`. The layers contract refuses the first and a forbidden contract the
  second, so a long-lived front end reaches the engine without loading the command line.

## Examples

```python
# ❌ Bad — the run hands a rule the database: the rule can read any document, so nothing bounds what a change
# to one file invalidates, and a unit test needs a whole snapshot to test a rule about one heading
for enabled in table.document_rules_governed_by(Facet.OUTLINE):
    for occurrence in enabled.rule.check_in(database, source):
        diagnostics.append(RuleDiagnostic(source.ref.path, occurrence, enabled.severity))
```

```python
# ✅ Good — the run resolves the rule's query and hands the rule its facts; a unit test hands it a literal
if ItemFacet.OUTLINE in source.descriptor.active_facets:
    for enabled in table.document_rules_governed_by(Facet.OUTLINE):
        facts = database.query(enabled.rule.query(), source.ref)
        for occurrence in enabled.rule.judge(facts):
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

```python
# ❌ Bad — a policy parameter matched inside the shared runner: the next mode adds a member and edits the
# runner every mode shares
def judge_item(database, source, table, policy: LoadFailurePolicy) -> SubjectReport:
    if policy is LoadFailurePolicy.SKIP and governance.failed_layers:
        return SkippedSubject(source.ref)
```

```python
# ✅ Good — each mode's policy is its own entry point over the shared runner, which takes no policy
def check_subjects(database, subjects, table) -> tuple[SubjectReport, ...]:
    ...  # skip.py: the check run's policy, then runner.judge_item(database, source, table)
```

## Checklist

Before committing code, verify:

- [ ] Nothing added memoizes a value derived from the snapshot; such a value is a query in `lorecraft.project`
- [ ] A rule is handed the facts of its query, never the database, a view or a path it could read through
- [ ] A queried Markdown item, symlink or corpus directory is dispatched through the same query and `judge` path
- [ ] A run attaches the subject's path to each occurrence; an occurrence names no subject
- [ ] Nothing added takes a snapshot or sets an exit code
- [ ] A mode's policy sits in that mode's own entry point; `runner.py` takes no policy parameter and no callback
- [ ] A new load-failure condition is reported by `load_failures.py`, whose match stays exhaustive, and a skipped
  document names each failed layer's structure file
- [ ] A document, skill or resource is decoded by each mode's entry point, so its policy comes after decoding; the
  item is asked for by its common reference, and failed corpus governance can skip documents or suppress skill
  corpus rules while preserving the Agent Skills floor; `runner.py`
  decodes nothing
- [ ] `judge_item` asks a rule its kinds and facet, never its base; only building the report matches on the kind
- [ ] Nothing here imports `lorecraft.cli` or `typer`

## References

- [adr-001-snapshot-model](../arch/adr-001-snapshot-model.md) - Foundation: The package roles
- [adr-012-database-derivation](../arch/adr-012-database-derivation.md) - Foundation: The Analysis role, the database
  apart
- [adr-016-specifications](../arch/adr-016-specifications.md) - Foundation: A rule applies the governing structure files its query returns
- [adr-010-diagnostics](../arch/adr-010-diagnostics.md) - Foundation: Diagnostics apart from failures
- [adr-015-database](../arch/adr-015-database.md) - Foundation: One report reads one revision, and skip or partial is the
  consumer's policy
- [principle-single-responsibility](principle-single-responsibility.md) - Foundation: One reason to change
- [pattern-memoization](pattern-memoization.md) - Foundation: How a query is memoized
