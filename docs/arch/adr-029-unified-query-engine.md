---
name: "adr-029-unified-query-engine"
description: "One declared-query engine for every derived fact and subject, with raw input primitives, subject-qualified reads, shared composition and one typed dispatch. Load when changing database query layers, primitive protocols, read recording, memoization or runner query dispatch"
type: "adr"
status: "proposed"
---

# One Engine for Derived Queries

> [!NOTE]
> Proposed to supersede in part [adr-015](adr-015-database.md), “Every Question Is a Query”: the statement that
> every query is a database method, and the per-file and analysis layers' method-based computation and carry-over.
> ADR-015 stays binding until this record is accepted; its revision, snapshot, decode and input boundaries remain.

## Context

ADR-015 layers input reads, per-file facts and analyses as database queries. ADR-026 adds declared queries with
generic memoization and carry-over derived from recorded reads. ADR-027 requires primitives to expose raw state
and derived facts to compose as queries. The implementation still has both mechanisms: per-file derived methods
keep dedicated caches, while declared queries share an answer-and-read-set table. Syntax and count primitives
conceal computations behind apparent raw reads.

Read recording and composition also differ by subject. Item reads retain their reference, layout primitives use
bare primitive names, and schema reads have separate records and tuples. Composition operations available to item
queries are missing from other subject protocols. The database and runner each dispatch by subject and use casts
to recover relationships their combined signatures have erased.

The design must preserve pure queries, precise subject-specific typing, the decode witness and rule judgments
over facts. Schema subjects already participate in the database; the proposed registry design in
[adr-028](adr-028-schema-registry.md) explains their input boundary. This record does not accept that separate
proposal or expand its schema policy.

## Decision

1. **D1 — Only input queries remain database methods.** A method is an input query when it reads snapshot
   state or returns model-held state. This boundary retains `model()`, `item_text`, `skill_resources`,
   `item_link_targets`, `item_governance`, and the schema-input, symlink and corpus-directory record lookups.
   Construction, registration, reporting accessors and query evaluation remain database operations; they do not
   justify adding derived-fact methods.

   Every other fact is a declared query. Project-owned facts live in `lorecraft.project.query`: frontmatter,
   parse, headings, links, anchors, token and line counts, item name and corpus, and structure specifications.
   Rule-group facts retain ownership-based placement under ADR-026 decision 6 and ADR-027 decisions 5–6.
   Compose existing facts through `primitives.query(...)` instead of recomputing them. All declared answers use
   the same memo table, keyed by query callable and subject, with recorded reads. No derived fact has a separate
   database cache or handwritten carry-over rule.

   Primitives expose raw subject, model or input-query state only, without an exception for syntax, counts or
   governance projections. Input queries alone state their carry-over rules; every declared query derives its
   carry-over from its recorded primitive and nested-query reads, applying ADR-026 decision 8 consistently.
   `item_link_targets` remains an input because it consults snapshot records and scope, even though it consumes
   a declared parse query. It reuses that query through the database rather than restoring a parse-method cache.

2. **D2 — One read key always names a subject.** Use one frozen
   `Read(source: PrimitiveRead | query, subject: SubjectRef)` for primitive and declared-query dependencies.
   `SubjectRef` covers Markdown-item, schema, symlink and corpus-directory references. A bare primitive enum,
   schema-only read record or subject-specific tuple is not a second key shape. This replaces `QueryRead`,
   `SchemaInputRead` and the `ReadKey` / `QueryKey` unions. A memoized query's identity uses the same query-and-subject
   shape. Nested reads retain their source subject, including schema and cross-item dependencies; the enclosing
   query never relabels them as reads of itself. Preserve recording a nested dependency before evaluation and
   retaining its transitive reads after successful evaluation.

3. **D3 — One recording base, shared composition on every subject.** Merge `_ReadSet` and the adapters' shared
   state and recording machinery into one primitives base. Every subject protocol extends a `QueryPrimitives`
   facet supplying `query`, `query_at` and `query_schema`. Only the raw-state facet differs by subject.
   Same-subject composition retains that subject's precise query type; cross-subject composition keeps the
   query/reference pairing typed. Keep subject-specific protocols and overloads. Do not replace them with a
   generic subject-to-primitives mapping that erases which raw operations a query may call.

4. **D4 — One subject dispatch and one unchecked retrieval.** Keep per-subject `@overload`s on
   `Database.query`. The database alone selects the subject's primitives and evaluates its query. The runner
   calls `database.query(rule.query(), ref)` where the rule and reference are already typed, then passes the
   facts to `judge`. Remove `_judged`'s overloads, subject match and casts rather than moving that dispatch to
   another runner helper.

   The heterogeneous memo table has exactly one cast, on retrieval, isolated in one helper. Precede it with a
   `# SAFETY:` comment stating the invariant: an entry for this callable and subject is populated only by
   evaluating that callable with the primitives permitted by its overload, so retrieval has the callable's result
   type. Insertion, read recording and dispatch add no casts and do not widen types to `Any` to evade checking.

## Consequences

- Every derived fact has one evaluation and dependency mechanism. Adding one no longer adds a database method,
  cache dictionary or handwritten invalidation assertion. Calls and integration tests using removed methods must
  use declared queries instead.
- Read sets become homogeneous across subject kinds, and composition becomes available to every subject.
  Dependency tests must distinguish equal primitive names read from different subjects and retain nested reads,
  including schema references and failed nested lookups.
- The database's overloads preserve the relation between a subject and its available primitives. The shared
  base removes recording duplication without promising identical raw operations for different subjects.
- The runner still owns evaluation order, applicability and diagnostic placement. Rules receive only typed
  facts. `ItemText` / `Undecodable` remains at the decode and runner boundary: queries neither construct witnesses
  nor introduce a second decode. Invalid-UTF-8 handling and rule-case diagnostics must remain compatible.
- A frontmatter-only query continues to read decoded text without requiring the full parse. Counts remain
  functions of whole-file text. Memoization consolidation must not introduce unnecessary parse work.
- Read sets describe future invalidation; this change implements neither `Database.advance` nor cross-revision
  result reuse. Input-query caches and snapshot ownership remain database responsibilities.

## Alternatives Considered

- **Keep the two mechanisms.** This avoids call-site migration, but derived facts still require hand-maintained
  caches and dependency prose, and raw primitives still conceal computations. It leaves ADR-027 decision 3
  incompletely applied.
- **Normalize read records alone.** This gives every dependency a subject, but retains asymmetric composition,
  duplicate runner dispatch and the separate per-file memo system.
- **Use one generic subject-to-primitives mapping.** This appears smaller, but a Python protocol cannot vary its
  methods by a subject type argument. Losing precise raw facets or recovering them with additional casts fails
  the type-safety constraint; retain explicit overloads and shared implementation instead.

## Checklist

- [ ] Only snapshot/model input queries remain fact-producing database methods; derived facts are declared queries
- [ ] Project-owned facts live in `lorecraft.project.query`; rule-owned facts retain ownership-based placement
- [ ] Primitives expose raw state only, and composition reuses existing queries
- [ ] Declared answers share one memo table and derive carry-over from recorded reads
- [ ] Every primitive and nested-query read uses the same frozen source-and-subject key
- [ ] Every subject protocol includes typed composition through the shared primitives base
- [ ] Subject-specific database overloads remain precise; no generic mapping erases raw facets
- [ ] Only the database dispatches query evaluation by subject; typed runner sites call it directly
- [ ] One retrieval helper contains the memo table's sole cast and its preceding `# SAFETY:` invariant
- [ ] Witness ownership, invalid-UTF-8 behavior and rule-case diagnostics are preserved
- [ ] Frontmatter-only and count queries require no full parse; no cross-revision reuse is introduced

## References

- [adr-015](adr-015-database.md) - Proposed to supersede in part: Method-based per-file and analysis query layers
- [adr-026](adr-026-rule-owned-queries.md) - Foundation: Pure declared queries, ownership and derived carry-over
- [adr-027](adr-027-subject-keyed-queries.md) - Foundation: Raw primitives, typed subjects and query composition
- [adr-028](adr-028-schema-registry.md) - Related proposal: Typed schema inputs in the common database mechanism
- [adr-005](adr-005-incremental.md) - Foundation: Input carry-over and revision boundaries
