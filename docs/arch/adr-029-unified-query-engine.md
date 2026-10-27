---
name: "adr-029-unified-query-engine"
description: "One declared-query engine for every fact a rule reads and every subject it reads it from: a rule names a parameterless query and judges the typed facts the runner resolves through the database, never a context; queries are pure functions over raw-state primitives in lorecraft.project.query, keyed by their Markdown item, symlink, corpus-directory or schema subject, live beside the rule group or layer that owns them, and share one memo table whose carry-over derives from subject-qualified recorded reads. Load when adding a fact a rule reads, adding or changing a query, primitive, subject kind or cross-item read, or changing database query layers, read recording, memoization or runner query dispatch"
type: "adr"
status: "accepted"
---

# One Engine for Derived Queries

> [!NOTE]
> Supersedes [adr-026-rule-owned-queries](adr-026-rule-owned-queries.md) and
> [adr-027-subject-keyed-queries](adr-027-subject-keyed-queries.md), whose decisions are restated here.
>
> Supersedes in part [adr-009-rules](adr-009-rules.md), [adr-011-rules-engine](adr-011-rules-engine.md) and
> [adr-012-database-derivation](adr-012-database-derivation.md): where a fact a rule reads is declared, computed and
> memoized, and how a run coordinates rule evaluation without subject contexts; and
> [adr-015-database](adr-015-database.md), “Every Question Is a Query”: the statement that every query is a database
> method, the per-file and analysis layers' method-based computation, and the stated carry-over of a derived fact.
> They stay binding for everything else; ADR-015's revision, snapshot, decode and input boundaries remain.

## Context

A rule originally read a fact of its subject through a method of the subject's context protocol, such as its title
constraints. Each fact was declared four times: as a method of the context protocol, as a query of the database, as
its implementation in the database context, and as a method of the fake context unit tests used. A rule was coupled
to every other rule reading the same fact through those shared declarations, and adding a rule requiring a new fact
edited four files outside the rule. The contexts (`DocumentContext`, `SkillContext`) also exposed internal project
model types (`Governance`, `StructureSpec`, `ParsedDocument`) to the rules layer, and each query stated its
carry-over by hand, in prose nothing checked against what it read.

Declared queries removed the contexts, but the query model then depended on the kind of subject judged. Markdown
items were resolved through the database while symlink and corpus-directory rules were judged directly, through
bases that duplicated the query-and-judgment contract. The primitive interface included facts already derived
from other facts, such as linked documents, frontmatter summaries, syntax and counts, concealing computations
behind apparent raw reads. A query reading another item recorded only the primitive name, not the item, so its
dependency was incomplete.

Two mechanisms also coexisted: ADR-015's per-file derived methods kept dedicated caches with handwritten
carry-over, while declared queries shared an answer-and-read-set table. Read recording and composition differed by
subject: item reads retained their reference, layout primitives used bare primitive names, and schema reads had
separate records. The database and runner each dispatched by subject and used casts to recover relationships their
combined signatures had erased.

The design must preserve pure queries, precise subject-specific typing, the decode witness and rule judgments over
facts. Schema subjects participate in the database as one more subject kind. Their input boundary, how schema inputs are
registered and resolved, is a separate design this record does not decide.

## Decision

1. **A rule names its query and judges facts.** A rule derives from the queried base of its subject kind and returns
   its query from `query()`, a `Query[Facts]`, and judges the facts in `judge(facts)`. It defines no
   `check(context)` and takes no subject context: the context protocols are retired, with no exception. Markdown-item,
   symlink and corpus-directory rules share the common `Queried` base and one contract.

2. **A query is pure, parameterless and keyed by its subject.** A subject is a Markdown item, a symlink, a corpus
   directory or a schema. A query takes only the primitives of its subject and returns the fact value object; it
   never reads the snapshot, a file or another query's cache directly. The database memoizes its answer by the pair
   of query callable and subject reference, so a new fact adds no database method, context method or fake method.

3. **Only input queries remain database methods.** A method is an input query when it reads snapshot state or
   returns model-held state. This boundary retains `model()`, `item_text`, `skill_resources`, `item_link_targets`,
   `item_governance`, and the schema-input, symlink and corpus-directory record lookups. Construction, registration,
   reporting accessors and query evaluation remain database operations; they do not justify adding derived-fact
   methods. `item_link_targets` remains an input because it consults snapshot records and scope, even though it
   consumes a declared parse query; it reuses that query through the database rather than restoring a parse-method
   cache.

   Every other fact is a declared query. Project-owned facts live in `lorecraft.project.query`: frontmatter, parse,
   headings, links, anchors, token and line counts, item name and corpus, and structure specifications.

4. **Primitives expose raw state only.** Primitive reads answer directly from the subject, the model or an input
   query, without an exception for syntax, counts or governance projections. A value computed from primitive values
   is a query, including a derived value shared by several rules. The `Query` signature and the primitive protocols
   live in `lorecraft.project.query`, not under schema validation, and are segregated into cohesive facets, so a
   query and its unit-test primitives depend only on the facets it reads.

5. **One recording base, shared composition on every subject.** One primitives base holds the shared state and
   read-recording machinery. Every subject protocol extends a `QueryPrimitives` facet supplying `query`, for
   same-subject composition, and one overloaded `query_at`, for item, symlink, corpus-directory and schema
   references. The matching `ItemQuery`, `SymlinkQuery`, `CorpusDirectoryQuery` and `SchemaQuery` aliases live
   beside the protocols in `lorecraft.project.query`; `SubjectQuery` is their union. Only the raw-state facet
   differs by subject. Same-subject composition retains that subject's precise query type; cross-subject
   composition keeps the query/reference pairing typed. Do not replace the subject-specific protocols and overloads
   with a generic subject-to-primitives mapping that erases which raw operations a query may call.

6. **A cross-subject read stays parameterless.** A query reads another subject by asking its primitives for
   `query_at(ref, query)`. The query itself takes no extra argument that would alter its memoization identity; the
   database records the dependency on the other subject instead. A back-link query, for example, asks the
   destination item for its `linked_paths` query and tests whether the source path is present.

7. **One read key always names a subject.** One frozen `Read(source: PrimitiveRead | query, subject: QueryTargetRef)`
   records primitive and declared-query dependencies alike, and `QueryTargetRef` covers Markdown-item, schema,
   symlink and corpus-directory references. A bare primitive enum, schema-only read record or subject-specific tuple
   is not a second key shape. A memoized query's identity uses the same query-and-subject shape. Nested reads retain
   their source subject, including schema and cross-item dependencies; the enclosing query never relabels them as
   reads of itself. A nested dependency is recorded before evaluation, and its transitive reads are retained after
   successful evaluation.

8. **Carry-over derives from recorded reads.** All declared answers share one memo table, keyed by query callable and
   subject, with their recorded reads. A declared query carries over to the next revision whenever every primitive
   and nested query it read does, so no declared query states a carry-over rule and no derived fact has a separate
   database cache. Input queries alone state their carry-over rules by hand.

9. **A query lives beside what owns it.** A query one rule group reads lives in that group's query module, keeping a
   new rule and its query local to the group. When a second group needs it, it moves to `lorecraft.project.query`,
   and both groups use the same callable, so the database keeps one memoized answer per `(query, subject)` pair. A
   fact that is the value of a layer lives in the layer that owns it; the engine resolves queries and does not own
   them merely because it runs them.

10. **Reuse an existing query before recomputing.** When a query needs a derived fact another query provides, it
    composes with that query through `primitives.query(...)` or `query_at` rather than reconstructing the fact from
    primitives.

11. **The database alone dispatches by subject.** `Database.query` keeps per-subject `@overload`s and selects the
    subject's primitives and evaluates its query. The runner calls `database.query(rule.query(), ref)` at call sites
    where the rule and reference are already typed, then hands the facts to `judge`. No runner helper overloads,
    matches on subject kind or casts to dispatch a query.

12. **One unchecked retrieval.** The heterogeneous memo table has exactly one cast, on retrieval, isolated in one
    helper and preceded by a `# SAFETY:` comment stating the invariant: an entry for this callable and subject is
    populated only by evaluating that callable with the primitives permitted by its overload, so retrieval has the
    callable's result type. Insertion, read recording and dispatch add no casts and do not widen types to `Any` to
    evade checking.

## Consequences

- The rules layer is decoupled from database mechanics, snapshot views and execution contexts: rules are pure
  functions from typed fact objects to diagnostic occurrences. `engine` imports `rules` and `project`, while `rules`
  never touches `engine` or the database.
- The facts are typed by the rule's type argument, and `query()` is checked against it: a rule whose query returns
  another type fails the type check.
- Every derived fact has one evaluation and dependency mechanism. Adding one adds no database method, cache
  dictionary or handwritten invalidation assertion, and a new subject kind participates through its subject
  reference and query facts instead of a second runner path.
- Read sets are homogeneous across subject kinds and distinguish query identity from subject reference, so a change
  to a referenced subject can invalidate the answers that read it. Dependency tests must distinguish equal primitive
  names read from different subjects and retain nested reads, including schema references and failed nested lookups.
- The database's overloads preserve the relation between a subject and its available primitives. The shared base
  removes recording duplication without promising identical raw operations for different subjects.
- The runner owns evaluation order, applicability and diagnostic placement. `ItemText` / `Undecodable` remains at the
  decode and runner boundary: queries neither construct witnesses nor introduce a second decode.
- A frontmatter-only query reads decoded text without requiring the full parse, and counts remain functions of
  whole-file text.
- Read sets describe future invalidation; this record implements neither `Database.advance` nor cross-revision
  result reuse. Input-query caches and snapshot ownership remain database responsibilities.

## Alternatives Considered

- **Keep subject contexts and forward through them.** A queried rule's `check(context)` that merely forwarded to
  `context.query(...)` kept context adapters in the evaluation path and every fact declared four times.
- **Keep the two memoization mechanisms.** This avoids call-site migration, but derived facts still require
  hand-maintained caches and dependency prose, and raw primitives still conceal computations.
- **Normalize read records alone.** This gives every dependency a subject, but retains asymmetric composition,
  duplicate runner dispatch and the separate per-file memo system.
- **Pass the other subject as a query argument.** It would change the query's memoization identity and hide the
  dependency from the read set; `query_at` records it instead.
- **Use one generic subject-to-primitives mapping.** This appears smaller, but a Python protocol cannot vary its
  methods by a subject type argument. Losing precise raw facets or recovering them with additional casts fails the
  type-safety constraint; explicit overloads and a shared implementation are retained instead.

## Checklist

Before committing code, verify:

- [ ] A rule names its query in `query()` and judges the facts in `judge(facts)`; it defines no `check(context)` and
  takes no subject context
- [ ] Every queried subject kind derives from the shared `Queried` base; no kind has a parallel direct judgment path
- [ ] A query is parameterless and pure over the primitives it takes, and never reads the snapshot, a file or another
  query's cache
- [ ] Only snapshot and model input queries remain fact-producing database methods; derived facts are declared
  queries
- [ ] Primitives expose raw state only; any derived answer is a query, and composition reuses existing queries
- [ ] `Query` and the primitive protocols live in `lorecraft.project.query`, in cohesive facets
- [ ] Every subject protocol includes typed composition through the shared primitives base
- [ ] A cross-subject read uses `query_at(ref, query)`, and every primitive and nested-query read is recorded under
  the same frozen source-and-subject key
- [ ] Declared answers share one memo table and derive carry-over from recorded reads; only input queries state a
  carry-over rule
- [ ] A rule group's queries begin in its group-level query module; a query a second group needs moves to
  `lorecraft.project.query` and both groups use the same callable
- [ ] Subject-specific database overloads remain precise; no generic mapping erases raw facets
- [ ] Only the database dispatches query evaluation by subject; typed runner sites call `database.query` directly,
  with no overload, subject match or cast in the runner
- [ ] One retrieval helper contains the memo table's sole cast and its preceding `# SAFETY:` invariant
- [ ] Witness ownership, invalid-UTF-8 behavior and rule-case diagnostics are preserved
- [ ] Frontmatter-only and count queries require no full parse; no cross-revision reuse is introduced

## References

- [adr-026-rule-owned-queries](adr-026-rule-owned-queries.md) - Supersedes: Rule-owned queries, pure judgments,
  query placement and derived carry-over
- [adr-027-subject-keyed-queries](adr-027-subject-keyed-queries.md) - Supersedes: Subject-keyed queries, raw
  primitives and cross-item reads
- [adr-009-rules](adr-009-rules.md) - Supersedes in part: How a rule reads the facts it judges
- [adr-011-rules-engine](adr-011-rules-engine.md) - Supersedes in part: Contexts, queries and runner orchestration
- [adr-012-database-derivation](adr-012-database-derivation.md) - Supersedes in part: Where a derived fact lives
- [adr-015-database](adr-015-database.md) - Supersedes in part: Method-based per-file and analysis query layers and
  their carry-over
- [adr-005](adr-005-incremental.md) - Foundation: Input carry-over and revision boundaries
- [pattern-memoization](../code/pattern-memoization.md) - Foundation: Memoizing a pure function
