---
name: "adr-026-rule-owned-queries"
description: "A rule names the query it needs, and the runner hands its judgement the typed facts that query returns, never a context: query functions are pure functions over model primitives, live beside the rule or group that owns them, and are memoized generically by the database. Load when adding a fact a rule reads, adding or changing a query, a context method or a fake context, or deciding what a query may carry over between revisions"
type: "adr"
status: "proposed"
---

# Rule-Owned Queries

> [!NOTE]
> Proposed to supersede in part [adr-009-rules](adr-009-rules.md), [adr-011-rules-engine](adr-011-rules-engine.md),
> [adr-012-database-derivation](adr-012-database-derivation.md) and [adr-015-database](adr-015-database.md): where a
> fact a rule reads is declared, computed and memoized, and how its carry-over is derived. They stay binding until
> this record is accepted.

## Context

A rule reads a fact of its subject through a method of the subject's context, such as `title_constraints()`. Each
fact is therefore declared four times: as a method of the context protocol, as a query of the database, as its
implementation in the database context, and as a method of the fake context the unit tests use. A rule is coupled to
every other rule that reads the same fact through those shared declarations, and adding a rule that needs a new fact
edits four files outside the rule.

Each query also states its own carry-over by hand, in prose, as the primitive it is "kept whenever" is kept. Nothing
checks that the prose matches what the query reads.

## Decision

1. **A rule names its query.** A rule derives from `QueriedDocumentRule[Facts]` and returns its query from
   `query()`, a `Query[Facts]`. The runner resolves it through the database and hands the rule's `judge` the facts and
   nothing else: `judge` takes no context, so everything the rule reads, such as the title, is in the facts. A rule
   that names no query is unchanged and reads the context as before.
2. **A query is a pure function over model primitives.** It takes the item's `Primitives`, the model state of the
   item such as its structure specifications, and returns the fact. It never reads the snapshot, a file or another
   query's cache.
3. **A query lives beside what owns it.** A query one rule or one rule group reads lives next to it. A fact several
   groups read is either a primitive of the model or a query in the layer that owns the value it returns.
4. **The database memoizes queries generically**, keyed by the function and the item, so a new query adds no
   database method, context method or fake method.
5. **Carry-over is derived from the primitives a query read.** The database notes which primitives each query read,
   and a query's answer is to carry over to the next revision whenever every one of them does, so no query states a
   carry-over rule of its own. Only the noting is implemented here.

## Consequences

- A rule is coupled to the others only through the model state its queries read.
- The context protocol keeps the primitives of a subject and `query`; a fact derived from them leaves it.
- The facts are typed by the rule's type argument, and `query()` is checked against it: a rule whose query returns
  another type fails the type check, which `typing_queried_rule.py` pins.
- The facts that remain methods of the context migrate one vertical at a time; until then a rule that names no query
  reads the context.
- Carrying an answer over to the next revision (`advance`) is not implemented by this record's first part; the
  database records which primitives a query read, and acting on it is a follow-up.

## References

- [adr-009-rules](adr-009-rules.md) - Supersedes in part: How a rule is declared
- [adr-011-rules-engine](adr-011-rules-engine.md) - Supersedes in part: Contexts and queries
- [adr-012-database-derivation](adr-012-database-derivation.md) - Supersedes in part: Where a derived fact lives
- [adr-015-database](adr-015-database.md) - Supersedes in part: The kinds of query and their carry-over
- [pattern-memoization](../code/pattern-memoization.md) - Foundation: Memoizing a pure function
