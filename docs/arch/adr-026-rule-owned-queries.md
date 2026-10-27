---
name: "adr-026-rule-owned-queries"
description: "A rule names the query it needs, and the runner resolves it through the database and hands its judgement the typed facts, never a context: queries are pure functions over cohesive primitive facets in lorecraft.project.query, live beside the rule or layer that owns them, and are memoized generically by the database while the runner coordinates evaluation directly. Load when adding a fact a rule reads, adding or changing a query or primitive, or changing how the runner resolves a rule's query"
type: "adr"
status: "superseded"
---

# Rule-Owned Queries

> [!NOTE]
> Superseded. It binds no code.
>
> Supersedes in part [adr-009-rules](adr-009-rules.md), [adr-011-rules-engine](adr-011-rules-engine.md),
> [adr-012-database-derivation](adr-012-database-derivation.md) and [adr-015-database](adr-015-database.md): where a
> fact a rule reads is declared, computed and memoized, how its carry-over is derived, and how a run coordinates rule
> evaluation without subject contexts. They stay binding for everything else. Superseded in part by
> [ADR-027](adr-027-subject-keyed-queries.md): decisions 2 and 7 (layout dispatch, memoization key).

## Context

A rule originally read a fact of its subject through a method of the subject's context protocol, such as
its title constraints. Each fact was declared four times: as a method of the context protocol, as a query of the
database, as its implementation in the database context, and as a method of the fake context unit tests used. A rule
was coupled to every other rule reading the same fact through those shared declarations, and adding a rule requiring a
new fact edited four files outside the rule.

Furthermore, context objects acted as leaky intermediaries: rules took subject contexts (`DocumentContext`,
`SkillContext`) exposing internal project model types (`Governance`, `StructureSpec`, `ParsedDocument`) directly into
the rules layer. When query rules were first introduced, `QueriedDocumentRule.check(context)` merely forwarded to
`context.query(cls.query())`, preserving context adapters in the evaluation path instead of letting the engine runner
coordinate database query resolution and rule judgment directly. Core query abstractions (`Query` and `ItemPrimitives`)
also resided in `lorecraft.project.schemas`, coupling syntax, links, and length rules to the schema validation
subpackage, while `ItemPrimitives` gathered disparate model capabilities into a single monolithic protocol.

Each query also stated its own carry-over by hand, in prose, as the primitive it is "kept whenever" is kept. Nothing
checked that the prose matched what the query read. A database query still states it, as it reads an input; a declared
query a rule owns now takes its carry-over from what it read.

## Decision

1. **A rule names its query and judges pure facts.** A rule derives from `QueriedDocumentRule[Facts]` (or the
   corresponding queried base for skills, markdown files, skill entrypoints, or frontmatter) and returns its query from
   `query()`, a `Query[Facts]`. A queried rule defines no `check(context)` method: it exposes only `query()` and
   `judge(facts)`.
2. **The runner coordinates query resolution directly.** The rules engine runner (`lorecraft.engine.runner`) resolves
   each rule's query through `database.query(rule.query(), ref)` and hands `rule.judge(facts)` the returned facts. No
   context object is instantiated: every rule names a query, and the subject context protocols are retired. The rules
   over layout entries, LC101 and LC102, are queried rules too: the runner hands each the facts of its query over the
   record of its entry (`_judged_symlink`, `_judged_directory`).
3. **Core query types live in `lorecraft.project.query`.** The `Query[T]` callable signature and the model primitive
   protocols are defined in `lorecraft.project.query` rather than `schemas`, making query definitions available across
   all project facets without coupling them to schema validation.
4. **ItemPrimitives are segregated into cohesive facets.** Rather than a single monolithic protocol, model primitives are
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
8. **Carry-over of a rule-owned query is derived from the primitives it read.** For a query a rule owns, run through
   `Database.query(query, ref)`, the database notes which primitives it read, and its answer carries over to the next
   revision whenever every one of them does (`query_reads`), so no such query states a carry-over rule of its own. The
   primitives it reads are database queries, such as `item_governance(ref)`, and each of those states its own
   carry-over rule by hand.

## Consequences

- The rules layer is completely decoupled from database mechanics, snapshot views, and execution contexts: rules
  operate as pure functions from typed fact objects to diagnostic occurrences.
- The engine runner owns the orchestration of database query fetching and rule judgment, fulfilling true unidirectional
  dependency flow: `engine` imports `rules` and `project`, while `rules` never touches `engine` or `database`.
- The context protocols (`DocumentContext`, `SkillContext`, `DatabaseItemContext`) are removed, with no exception. The
  rules over layout entries, LC101 and LC102, read the record of their entry through a query like any other rule;
  the record is one the model already holds, so there is nothing to memoize and no Markdown item to key a query by.
- Query abstractions are cleanly decoupled from `lorecraft.project.schemas`.
- The facts are typed by the rule's type argument, and `query()` is checked against it: a rule whose query returns
  another type fails the type check.
- Carrying a rule-owned answer over to the next revision (`advance`) uses the recorded primitive read set, grounded in
  observed reads rather than a handwritten docstring assertion. The database queries beneath it still state their own
  carry-over rules by hand.

## Checklist

Before committing code, verify:

- [ ] A rule names its query in `query()` and judges the facts in `judge(facts)`; it defines no `check(context)` and
  takes no subject context
- [ ] The runner resolves a rule's query through `database.query(rule.query(), ref)` and hands the facts to the
  rule's `judge`, with no context object built for it
- [ ] The rules over layout entries, LC101 and LC102, are queried rules too: the runner hands each the facts of its
  query over the record of its entry, and no query for them is keyed by a Markdown item
- [ ] A query is a pure function over the primitive facets it takes, and never reads the snapshot, a file or another
  query's cache
- [ ] A query lives beside the rule or layer that owns it, and `Query` and the primitive protocols live in
  `lorecraft.project.query`
- [ ] A new fact adds no database method, context method or fake method: the database memoizes the query by the
  function and the item reference
- [ ] A declared query run through `Database.query` states no carry-over rule: it carries over whenever every
  primitive it read does, as `query_reads` records
- [ ] A database query that a declared query reads, such as `item_governance(ref)`, still states its own carry-over
  rule

## References

- [adr-009-rules](adr-009-rules.md) - Supersedes in part: How a rule is declared
- [adr-011-rules-engine](adr-011-rules-engine.md) - Supersedes in part: Contexts, queries, and runner orchestration
- [adr-012-database-derivation](adr-012-database-derivation.md) - Supersedes in part: Where a derived fact lives
- [adr-015-database](adr-015-database.md) - Supersedes in part: The kinds of query and their carry-over
- [adr-027-subject-keyed-queries](adr-027-subject-keyed-queries.md) - Supersedes in part: Layout dispatch and the
  memoization key in decisions 2 and 7
- [pattern-memoization](../code/pattern-memoization.md) - Foundation: Memoizing a pure function
