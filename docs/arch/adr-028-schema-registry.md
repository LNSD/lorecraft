---
name: "adr-028-schema-registry"
description: "Define typed schema inputs and query-visible schema dependencies under `lorecraft.schemas`, with database-owned memoization and built-in schemas on the normal registry path. Load when adding or changing schema inputs, registry resolution, schema query subjects or schema validation"
type: "adr"
status: "proposed"
---

# Central Schema Registry

## Context

Schema input loading and validation are spread across workspace loading, structure specifications, frontmatter
queries and built-in skill handling. The project already has a schema repository boundary that reads through the
workspace file system, and its database memoizes queries by callable and subject while recording nested reads.
Schemas do not yet have a typed subject in that query model.

Two kinds of schema input must remain distinct. A structure schema describes Lorecraft's specification dialect;
its `frontmatter` member can itself contain a JSON Schema. These inputs have different validation semantics and
must not be treated as interchangeable. Parsed structure specifications, and facts such as outline and budget
results, remain owned by their existing project domain.

The accepted database and query decisions establish the constraints for this design. ADR-015 keeps query answers
and read sets in a database's memoization table and reserves `advance` for a future database lifecycle. ADR-026
keeps query definitions with the layer that owns their returned values. ADR-027 keys queries by typed subject and
records cross-subject reads as typed query/subject pairs. The registry must fit those rules without becoming a
second cache or requiring cross-revision advancement now.

ADR-022 also governs skills. Its built-in floor has a distinct bundled origin, applies independently from
repository layers, supports a global opt-out, uses bounded contradiction preflight, and preserves skill-specific
validation findings. Currently the skills floor uses Pydantic while repository frontmatter schemas use JSON
Schema. Moving built-ins onto the registry path does not by itself establish that their validators or diagnostics
are interchangeable.

## Decision

1. **One registry API lives under `lorecraft.schemas`.** It represents typed validation schema inputs and resolves
   them by a Lorecraft-owned schema reference. A reference identifies the schema kind and stable source identity;
   it does not depend on an invented filesystem path or on a JSON Schema `$id`.
2. **Schema kinds remain explicit.** Registry entries distinguish at least repository structure-schema inputs,
   frontmatter JSON Schema inputs, and bundled built-in schema inputs. A structure schema is not a frontmatter
   JSON Schema. Parsed `StructureSpec` values and outline, budget, or other domain facts are not registry entries.
3. **Origin is part of each registry entry.** Repository entries retain their repository path and governing layer
   identity. Bundled entries carry a bundled origin and stable built-in identity. Built-ins use the same registry
   lookup and query path as repository schemas; they are ordinary schemas distinguished by their origin, not by
   being user-provided.
4. **The registry package owns schema vocabulary and pure schema operations, not project queries.** Types such as
   schema kind, schema reference, origin, and immutable schema input live under `lorecraft.schemas`. That package
   may use Lorecraft's JSON Schema adapter where appropriate, but does not import project database, project query,
   or workspace-loading modules. Project query definitions and subject dispatch may depend on these schema types.
   This keeps the dependency direction acyclic.
5. **Schema reads are typed query subjects.** The project query layer exposes schema facts as parameterless
   queries keyed by a schema subject reference. A query that validates an item reads the applicable schema facts
   through the database query operation. Each cross-schema read is recorded by the pair `(query callable,
   schema subject reference)`, alongside the existing item query dependencies. No validation query reads the live
   filesystem directly.
6. **The database remains the only memoization owner.** Schema queries use the existing database memoization
   table and its `(query callable, subject reference)` identity. The registry does not hold a second cache, and
   existing within-database memoization behavior remains unchanged. Query read sets retain schema subject identity
   so a future `advance` implementation can compare the schema dependencies of old and new database revisions.
   Implementing `Database.advance` or reusing memoized results between databases is outside this decision.
7. **Bootstrap separates raw input acquisition from derived schema queries.** Workspace loading continues to read
   source bytes through the existing file-system-backed repository boundary and records immutable schema inputs
   with their typed references and origins in the loaded model. It does not create a second parsed-schema cache.
   Once a database exists, schema parsing, resolution and validation facts that participate in checks are obtained
   through its schema queries. Existing loading of parsed structure specifications and their failure records stays
   in the structure-specification domain; the registry does not take ownership of those parsed values.
8. **Applicability remains a project concern.** Project queries determine which typed schema references apply to
   an item or layer from the loaded model's governance data, then compose the corresponding schema queries. The
   registry resolves a reference to its input and kind; it does not duplicate namespace matching, governed-item
   discovery, failed-layer policy, or outline and budget computations.
9. **Built-in skill behavior remains compatible.** The skills floor is represented by a bundled-origin registry
   entry and participates in the same lookup and dependency model. Its current Pydantic validation, finding
   wording, independent application beside repository layers, global opt-out, bounded contradiction preflight,
   and duplicate-field suppression remain as specified by ADR-022. A later change may unify validator backends
   only with evidence that accepted values and diagnostics are preserved; generated JSON Schema alone is not
   such evidence.
10. **Schema references do not expand JSON Schema resource policy.** An internal registry reference is not a
    JSON Schema `$id`. Existing restrictions on external references, dialects, and resource boundaries remain in
    force. Registry resolution is local to loaded repository inputs and bundled definitions.
11. **The Agent Skills floor schema enters via bootstrap pre-registration.** Pre-registration supplies the bundled
    Agent Skills floor schema input during workspace model loading. The global opt-out (`--no-builtin-skills-schema`)
    is achieved by omitting the pre-registered floor schema input from the loaded model's schema inputs. When
    omitted, the active schema registry simply contains no entry for the floor schema reference; absence is a
    normal registry state rather than an error.
12. **Boolean flag plumbing is eliminated across downstream layers.** Because the presence or absence of the floor
    schema is fully captured by the schema registry entries in the loaded model, `check_skill_compatibility` and
    `builtin_skills_schema` boolean parameters are removed from `loader.py`, `model.py`, `database.py`,
    `primitives.py`, and `runner.py`. Downstream layers (database query primitives, frontmatter queries, engine rule
    runners, inspect command formatting) determine whether the floor applies by querying registry presence for the
    floor schema reference rather than inspecting a propagated boolean flag.
13. **Bounded compatibility preflight is a project-owned operation.** During loader bootstrap, when the pre-registered
    floor schema input is present, a project schema operation (`project/schemas`) evaluates candidate repository skills
    layers against the active floor schema reference using ADR-022's bounded direct-field analysis (`name` and
    `description` string constraints). The preflight operation returns contradictions to the loader, which records
    them via its existing failed-structure mechanism (`_record_failed_structure`). When the floor schema is not
    pre-registered, no compatibility preflight is executed and no contradiction can occur. `lorecraft.schemas` does
    not execute compatibility checks, compose layers, or enforce failed-layer policy.
14. **One query resolves an item's applicable frontmatter schemas.** An item query resolves its applicable frontmatter
    schemas as an ordered tuple of `SchemaRef`: any bundled floor schemas declared for its kind (such as the Agent
    Skills floor for skill entrypoints, when pre-registered), followed by each loaded governing layer's frontmatter
    schema from broad to narrow. Every schema in the tuple is read through the `query_at` operation with the schema reference.
    Repository frontmatter schemas are no longer read through a separate structure-spec wrapper.
15. **One locator maps schema violations to located problems with progressive deduplication.** Rather than maintaining
    kind-specific locators, one frontmatter schema locator validates frontmatter against each applicable schema in the
    tuple. Missing-field diagnostics are deduplicated progressively: a missing-field violation is suppressed if any
    earlier schema in the tuple already reported a missing field on the same line. Differences in validator backends
    (JSON Schema for repository schemas and Pydantic for the Agent Skills floor) produce uniform `FrontmatterProblem`
    instances and do not obstruct shared location or progressive deduplication.
16. **Frontmatter governance and rule gates are uniform across all item kinds.** An item is governed for
    `MetaSpecPart.FRONTMATTER` exactly when its applicable frontmatter schema tuple is non-empty. Every frontmatter
    rule, including `name_mismatch`, declares `WhenMetaSpec(MetaSpecPart.FRONTMATTER)` for every governed item kind.
    `name_mismatch` is treated as a general invariant of Lorecraft-governed frontmatter: when an item's frontmatter is
    governed by any schema, a written string `name` must equal the item's aspect name (its filename for documents, or
    its directory name for skills). `WhenSchema` is no longer used by frontmatter rules.

### Design Shape

The intended flow is:

```text
workspace FileSystem
        │ reads repository schemas
        │
bundled Agent Skills schema
        │ pre-registered at bootstrap (omitted if opted out)
        ▼
project preflight ── bounded contradiction check ──► loader records failed layers
        │
        ▼
loaded model: typed schema inputs + origin + governance data
        │
        ▼
Database ── memoized schema query(schema subject) ──► schema facts
        ▲                                                   │
        └──────── item validation query reads facts ────────┘
```

The diagram separates ownership. The loader supplies immutable raw inputs and project governance data, pre-registering
bundled schemas unless opted out. Project-owned preflight evaluates candidate skills layers against the pre-registered
floor before recording failed layers. Schema queries produce memoized derived facts. Item queries record dependencies
on the schema subjects they actually read. Downstream query and engine consumers test registry presence instead of
carrying boolean flags. The registry is a lookup and type boundary; it does not independently memoize parsed or validated
results.

### Alternatives Considered

- **Keep an immutable registry only in the loaded model.** This is the smallest migration and preserves coarse
  model rebuilds, but schema dependencies are not first-class query reads. It cannot prepare precise read sets for
  future database advancement and leaves schema access split between consumers.
- **Use typed schema subjects in the existing query mechanism.** Chosen. It adds subject/reference and dispatch
  work, and bootstrap must be explicit, but it gives schemas tracked dependencies while preserving the database
  as the sole memoization owner and keeps the query model extensible for future advancement.
- **Use a third-party resource registry as the architecture.** A resource map can resolve identifiers to schema
  resources, but it does not provide Lorecraft source governance, failure policy, query dependencies or
  memoization. It also crosses the current dependency containment boundary. It may be used inside an owned adapter
  only if a separate dependency-boundary decision permits it; it is not the project registry architecture.
- **Keep contradiction preflight directly inside loader structure loops.** Rejected. Having `loader.py` coordinate
  skills-specific schema contradiction analysis across multiple helper functions couples loader parsing with
  skill domain rules.
- **Put layer composition and contradiction preflight into `lorecraft.schemas`.** Rejected. Coupling contradiction
  detection to `SchemaRegistry` registration would violate decision 4 by placing project governance and failure
  policy inside pure schema utilities. Option 2 (a project-owned preflight operation invoked at bootstrap) preserves
  architectural separation.

## Consequences

- Schema resolution and validation facts gain one typed entry point, and built-in schemas no longer need a
  separate lookup branch. Their bundled origin remains visible without a fabricated file path.
- Adding schema subjects extends the database's subject/reference and read-set types and query dispatch. This is
  migration work across the schema, project query and database boundaries; it must not introduce a parallel cache
  or a direct filesystem path inside derived queries.
- Keeping raw inputs in the loaded model and parsed structure specifications in their existing domain avoids a
  registry/database bootstrap cycle. It also means loader parsing and database schema queries have distinct roles
  that must be documented and tested at their boundary.
- Pre-registering the Agent Skills floor schema into the loaded model makes opt-out a simple omission of the
  bundled input at the bootstrap edge, eliminating redundant boolean plumbing across loader, model, database, and
  engine layers.
- Bounded contradiction preflight remains owned by the project schema layer; the pure registry remains unaware of
  governance policy or failure recording.
- Explicit kind and origin make the model more verbose but prevent a structure dialect from being mistaken for
  JSON Schema and prevent built-in provenance from being lost.
- The design prepares schema read sets for future cross-revision carry-over, but does not deliver cross-revision
  reuse or invalidation until `advance` is separately implemented.
- Preserving two existing validation backends limits migration risk. It also means uniform registry lookup does
  not promise uniform validation behavior; the skills floor keeps its current compatibility contract.
- Local-only registry resolution retains deterministic, offline behavior and the existing restriction against
  cross-resource `$ref` resolution.
- Resolving applicable schemas as an ordered tuple of schema references and querying each via `query_at` with the schema reference
  unifies the validation query and problem location across bundled and repository schemas, eliminating kind-based
  branches from `frontmatter_schema_problems`.
- Progressive missing-field deduplication across earlier schemas in the tuple generalizes floor-only suppression
  to any combination of bundled and repository layers.
- Gating all frontmatter rules on `WhenMetaSpec(FRONTMATTER)` establishes complete gate homogeneity across item kinds
  and removes `WhenSchema` from frontmatter rules.

## Deferred

- Implementing `Database.advance`, cross-revision memo carry-over, and its invalidation algorithm.
- Replacing the skills Pydantic validator with JSON Schema or asserting backend equivalence without differential
  diagnostic and acceptance evidence.
- Remote schema loading, cross-resource references, general schema satisfiability analysis, and ownership of
  outline or budget facts.

## Checklist

- [ ] Registry references distinguish schema kind and stable identity; entries preserve repository or bundled
      origin without inventing a path or `$id`
- [ ] Structure schemas, frontmatter JSON Schemas, and bundled schemas remain distinguishable typed inputs
- [ ] Parsed structure specifications and outline/budget facts remain in their existing domain
- [ ] Workspace inputs enter through the file-system-backed repository boundary; derived queries do not read the
      live filesystem
- [ ] Schema queries use the project database and are memoized only by its `(query callable, subject reference)`
      key
- [ ] Cross-schema reads are represented in the read set by typed schema subject references and compose through
      the existing query operation
- [ ] Registry package dependencies do not point to project query, database, or workspace-loading modules
- [ ] Loader bootstrap does not add a second parsed-schema cache and keeps existing structure parse failures
      governed by the structure-specification domain
- [ ] Built-in skills use registry resolution with bundled origin and preserve ADR-022 validation behavior,
      diagnostics, independent layers, opt-out, bounded preflight, and duplicate-field suppression
- [ ] The Agent Skills floor schema is pre-registered during bootstrap and omitted when opting out, without
      propagating `check_skill_compatibility` or `builtin_skills_schema` boolean flags downstream
- [ ] Bounded compatibility preflight is executed by a project-owned operation against the pre-registered floor
      schema input and reported to the loader's failed-structure records, keeping `lorecraft.schemas` free of
      project governance and failure policy
- [ ] Applicable frontmatter schemas are resolved as an ordered tuple of `SchemaRef` and read through `query_at` with the schema reference,
      for both bundled floor schemas and repository layers
- [ ] Frontmatter schema problems are located by one locator that deduplicates missing-field findings progressively
      across earlier schemas in the tuple
- [ ] `MetaSpecPart.FRONTMATTER` is governed exactly when an item's applicable frontmatter schema tuple is non-empty,
      and all frontmatter rules use `WhenMetaSpec(FRONTMATTER)` for every governed item kind
- [ ] Schema subject identities and read sets can be compared across database revisions by a future `advance`
      implementation; this ADR does not implement advancement
- [ ] Internal schema references do not enable external JSON Schema resources or change current dialect and
      reference restrictions

## References

- [adr-015](adr-015-database.md) - Foundation: Database lifetime, memoization ownership and reserved advancement
- [adr-022](adr-022-skills-governance.md) - Constraint: Built-in skills origin, validation compatibility and
  governance behavior
- [adr-026](adr-026-rule-owned-queries.md) - Foundation: Query ownership and database-owned memoization
- [adr-027](adr-027-subject-keyed-queries.md) - Foundation: Typed query subjects and cross-subject read sets
