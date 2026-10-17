---
name: "adr-026-rule-owned-queries"
description: "A rule names the query it needs, and the runner resolves it through the database and hands its judgement the typed facts, never a context: queries are pure functions over cohesive primitive facets in lorecraft.project.query, live beside the rule or layer that owns them, and are memoized generically by the database while the runner coordinates evaluation directly. Load when adding a fact a rule reads, adding or changing a query or primitive, or migrating rules away from context methods"
type: "adr"
status: "proposed"
---

# Rule-Owned Queries

> [!NOTE]
> Proposed to supersede in part [adr-009-rules](adr-009-rules.md), [adr-011-rules-engine](adr-011-rules-engine.md),
> [adr-012-database-derivation](adr-012-database-derivation.md) and [adr-015-database](adr-015-database.md): where a
> fact a rule reads is declared, computed and memoized, how its carry-over is derived, and how a run coordinates rule
> evaluation without subject contexts. They stay binding until this record is accepted.

## Context

A rule originally read a fact of its subject through a method of the subject's context protocol, such as
`title_constraints()`. Each fact was declared four times: as a method of the context protocol, as a query of the
database, as its implementation in the database context, and as a method of the fake context unit tests used. A rule
was coupled to every other rule reading the same fact through those shared declarations, and adding a rule requiring a
new fact edited four files outside the rule.

Furthermore, context objects acted as leaky intermediaries: rules took subject contexts (`DocumentContext`,
`SkillContext`) exposing internal project model types (`Governance`, `StructureSpec`, `ParsedDocument`) directly into
the rules layer. When query rules were first introduced, `QueriedDocumentRule.check(context)` merely forwarded to
`context.query(cls.query())`, preserving context adapters in the evaluation path instead of letting the engine runner
coordinate database query resolution and rule judgment directly. Core query abstractions (`Query` and `Primitives`)
also resided in `lorecraft.project.schemas`, coupling syntax, links, and length rules to the schema validation
subpackage, while `Primitives` gathered disparate model capabilities into a single monolithic protocol.

Each query also stated its own carry-over by hand, in prose, as the primitive it is "kept whenever" is kept. Nothing
checked that the prose matched what the query read.

## Decision

1. **A rule names its query and judges pure facts.** A rule derives from `QueriedDocumentRule[Facts]` (or the
   corresponding queried base for skills, markdown files, skill files, or frontmatter) and returns its query from
   `query()`, a `Query[Facts]`. A queried rule defines no `check(context)` method: it exposes only `query()` and
   `judge(facts)`.
2. **The runner coordinates query resolution directly.** The rules engine runner (`lorecraft.engine.runner`) resolves
   each rule's query through `database.query(rule.query(), ref)` and hands `rule.judge(facts)` the returned facts. No
   context object is instantiated for queried rules. Legacy rules that name no query continue reading a context until
   migrated, after which subject context protocols are retired.
3. **Core query types live in `lorecraft.project.query`.** The `Query[T]` callable signature and the model primitive
   protocols are defined in `lorecraft.project.query` rather than `schemas`, making query definitions available across
   all project facets without coupling them to schema validation.
4. **Primitives are segregated into cohesive facets.** Rather than a single monolithic protocol, model primitives are
   composed of focused protocols (syntax ASTs, token and line counts, governance specifications, frontmatter blocks,
   and link resolution targets). The database primitive reader implements the composite interface, allowing queries
   and unit test primitives to depend only on the facets they read.
5. **A query is a pure function over model primitives.** It takes the item's primitive facet, the model state of the
   item such as its structure specifications, and returns the fact value object. It never reads the snapshot, a file,
   or another query's cache directly.
6. **A query lives beside what owns it.** A query one rule or one rule group reads lives next to it. A fact several
   groups read is either a primitive of the model or a query in the layer that owns the value it returns.
7. **The database memoizes queries generically**, keyed by the function and the item reference, so a new query adds no
   database method, context method or fake method.
8. **Carry-over is derived from the primitives a query read.** The database notes which primitives each query read,
   and a query's answer is to carry over to the next revision whenever every one of them does, so no query states a
   carry-over rule of its own.

## Consequences

- The rules layer is completely decoupled from database mechanics, snapshot views, and execution contexts: rules
  operate as pure functions from typed fact objects to diagnostic occurrences.
- The engine runner owns the orchestration of database query fetching and rule judgment, fulfilling true unidirectional
  dependency flow: `engine` imports `rules` and `project`, while `rules` never touches `engine` or `database`.
- Context protocols (`DocumentContext`, `SkillContext`, `DatabaseItemContext`) are deprecated and removed once all
  rules migrate to queries.
- Query abstractions are cleanly decoupled from `lorecraft.project.schemas`.
- The facts are typed by the rule's type argument, and `query()` is checked against it: a rule whose query returns
  another type fails the type check.
- Carrying an answer over to the next revision (`advance`) uses the recorded primitive read set; incremental carry-over
  logic is grounded in observed reads rather than handwritten docstring assertions.

## References

- [adr-009-rules](adr-009-rules.md) - Supersedes in part: How a rule is declared
- [adr-011-rules-engine](adr-011-rules-engine.md) - Supersedes in part: Contexts, queries, and runner orchestration
- [adr-012-database-derivation](adr-012-database-derivation.md) - Supersedes in part: Where a derived fact lives
- [adr-015-database](adr-015-database.md) - Supersedes in part: The kinds of query and their carry-over
- [pattern-memoization](../code/pattern-memoization.md) - Foundation: Memoizing a pure function
