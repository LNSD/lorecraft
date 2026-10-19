---
name: "adr-027-subject-keyed-queries"
description: "One composable query model for every rule subject: each query is parameterless and keyed by its Markdown item, symlink or corpus-directory subject; primitives expose raw model state, derived facts are queries, and cross-item reads are recorded. Queries start in their rule group and move to the project layer when another group needs them. Load when adding or changing a rule query, primitive, subject kind, cross-item read or runner query dispatch"
type: "adr"
status: "accepted"
---

# Subject-Keyed Queries

> [!NOTE]
> Supersedes in part [adr-026-rule-owned-queries](adr-026-rule-owned-queries.md), decisions 2 and 7: every
> rule subject uses the same query base and runner path, and the memoization key includes the subject. Decision 6
> remains binding: a query lives in the layer that owns the value it returns. ADR-026 remains binding for all
> other decisions.

## Context

Rule queries currently describe Markdown items well: the runner resolves each parameterless query with a
`ItemRef`, and the database memoizes the answer by query and item. Layout rules over symlinks and corpus
directories take a separate path, however. The runner judges those records directly, and their rule bases duplicate
the query and judgment contract rather than extending the common `Queried` base. The query model therefore depends
on which kind of subject happens to be judged.

The database's primitive interface also includes facts already derived from other facts. For example, linked
documents and frontmatter summaries are computations, not raw state. Keeping them as primitives makes them harder
to compose and reuse, and grows the primitive interface as derived answers are added.

Finally, a query may read another item while computing its answer. If the database records only the primitive query
name and not the referenced item, that dependency is incomplete: a later revision can change the other item while
the answer appears reusable. Queries need a way to express these reads without taking parameters that would alter
their memoization identity.

## Decision

1. **Every rule query is keyed by its subject.** A subject is a Markdown item, a symlink, or a corpus directory.
   The database accepts a query and the corresponding subject reference, and memoizes its answer by the pair of
   query and subject. The query remains a parameterless callable; the subject supplies the model state on which it
   operates.
2. **Every queried rule shares one base and runner path.** Markdown-item, symlink and corpus-directory rules derive
   from the common `Queried` base. The runner resolves each rule's query through the database for that rule's
   subject, then passes the returned facts to `judge`. It does not judge layout records through a separate path.
3. **Primitives expose raw model state only.** Primitive reads answer directly from the subject and model state.
   A value computed from primitive values is a query, including a derived value shared by several rules. A derived
   query may compose other queries through the primitive query operation; it is still memoized by the database.
4. **Cross-item reads use `query_at(ref, query)`.** A query reads another subject by asking its primitives for
   `query_at(ref, query)`. The query itself remains parameterless, while the database records the dependency as the
   typed pair `(query, ref)`. The read set therefore identifies both what was read and which subject supplied it.
   For example, a back-link query can ask the destination item for its `linked_paths` query and test whether the
   source path is present.
5. **A rule group owns its queries.** Each rule group's queries live in a group-level query module, keeping a new
   rule and its query local to that group. This follows ADR-026 decision 6: a query lives beside the rule or group
   that owns it, or in the layer that owns the value it returns.
6. **Promote a query when another group needs it.** When a second rule group needs a query, move it to
   `lorecraft.project.query`. Both groups then use the same query callable, so the database reuses one memoized
   answer for each `(query, subject)` pair. Project-owned primitives remain in `lorecraft.project.query`.
7. **Reuse an existing query before recomputing.** When a query needs a derived fact already provided by another
   query, compose with or reuse that query rather than reconstructing the fact from primitives.

## Consequences

- Markdown items, symlinks and corpus directories use the same database query mechanism, rule base and runner
  dispatch. A new subject kind participates through its subject reference and query facts instead of adding a
  second runner path.
- Queries stay parameterless, so the database's identity remains the query and the subject. A cross-item dependency
  is represented in the read set rather than hidden in an extra query argument.
- Read sets distinguish query identity and subject reference. Changes to a referenced subject can therefore
  invalidate answers that depend on it when carry-over uses those recorded reads.
- Primitive protocols remain a description of available raw model state. Derived facts can be named, composed,
  memoized and reused as queries without adding derived methods to the primitive interface.
- A query starts in the rule group's query module. When another group needs it, promotion to
  `lorecraft.project.query` gives both groups the same memoized answer for each `(query, subject)` pair.
- Rules remain pure judgments of typed facts. They do not read the database, primitives, or another subject; query
  composition and cross-item access happen below them.
- ADR-026 decision 6 continues to determine ownership-based placement. The engine resolves queries; it does not own
  them merely because it runs them.

## Checklist

Before committing code, verify:

- [ ] A query is parameterless and the database keys it by the query and its Markdown-item, symlink or
      corpus-directory subject
- [ ] Every queried subject kind uses the shared `Queried` base and runner path; no kind has a parallel direct
      judgment path
- [ ] Primitive reads expose raw model state; any derived answer is a query
- [ ] A cross-item read uses `query_at(ref, query)` and is recorded as the typed pair `(query, ref)`
- [ ] A query reads another query's result through the query operation and does not recompute an existing answer
- [ ] Each rule group's queries begin in a group-level query module, keeping a new rule local to its group
- [ ] When a second group needs a query, promote it to `lorecraft.project.query`; both groups use the same query so
      there is one memoized answer per `(query, subject)` pair
- [ ] Query placement follows ADR-026 decision 6; project primitives and cross-group queries live in
      `lorecraft.project.query`
- [ ] A rule receives only the facts of its named query and judges them without reading another subject

## References

- [adr-026-rule-owned-queries](adr-026-rule-owned-queries.md) - Foundation: Rule-owned queries, pure judgments,
  query placement and carry-over
- [adr-012-database-derivation](adr-012-database-derivation.md) - Foundation: Derivation and the database
- [adr-015-database](adr-015-database.md) - Foundation: A revision's database and query cache
- [pattern-memoization](../code/pattern-memoization.md) - Foundation: Memoizing a pure function
