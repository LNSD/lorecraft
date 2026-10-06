---
name: "adr-012-database-derivation"
description: "The database of a revision is derivation, not analysis: it moves with its decode witnesses and the database-backed contexts into the Derivation package, which may cache within a revision, and the Analysis package keeps the checks that judge the query results. Load when adding a query, a witness or a context implementation, deciding whether code belongs in lorecraft.project or lorecraft.checks, or reviewing what a package may cache"
type: "adr"
status: "accepted"
---

# The Database as Derivation

> [!NOTE]
> Supersedes in part [adr-001-snapshot-model](adr-001-snapshot-model.md): the Derivation and Analysis rows of its
> role table. The rest of adr-001 stays binding.

## Context

[adr-001](adr-001-snapshot-model.md) splits the work on one revision between two roles. Derivation, played by
`lorecraft.project`, turns what a view holds into values and never caches a result across calls. Analysis, played by
`lorecraft.checks`, holds the database of one revision and the checks that judge its query results.

Since [#410](https://github.com/LNSD/lorecraft/issues/410), that line runs through the middle of the database:

- **The queries are derivations of a revision.** The model, the decoded text, the parse tree, the counts and the
  shared analyses are each computed by a function of `lorecraft.project` already: `parse_document`, `count_tokens`,
  `locate_schema_problems` and `match_outlines` among them. The database only memoizes those functions for one
  snapshot, so it sits with what it memoizes, not with the rules or the run.
- **The database is check-agnostic.** No query is shaped around a rule or a check, so nothing ties it to the package
  that judges.
- **The contexts point down.** The context protocols a rule reads are declared in `lorecraft.project`, below
  `lorecraft.rules`. With the database in `lorecraft.checks`, their only implementation sat above both, so `rules`
  depended, through the interfaces, on a package above it.

The decode witnesses and the database-backed contexts cannot be split from the database. Only the database builds a
witness and every per-file query takes one; a context is a thin adapter over the queries.

## Decision

1. **Derivation holds the database.** The role reads:

   | Role | Does | Never |
   |---|---|---|
   | Derivation | Turns what a view holds into values: the model, a parse tree, a token count, a shared analysis. Holds the database of one revision, which memoizes those values as queries, the decode witnesses it hands out, and the database-backed contexts that answer the context protocols from its queries | Reads the disk, takes a snapshot, decides whether a value breaks a rule, or caches a result across revisions |

   A query may cache its result for the lifetime of its database, one revision. Nothing carries over to the next
   revision or persists across processes yet; the carry-over rules and the store of
   [adr-005](adr-005-incremental.md) are the one way a result ever will, and they are the database's, in this
   package.
2. **Analysis keeps the judgment.** The role reads:

   | Role | Does | Never |
   |---|---|---|
   | Analysis | Holds the checks that judge the query results: the rules, the runner that hands each rule its subject, the rule table, level resolution and the reports | Takes a snapshot, prints, memoizes a value derived from the snapshot, or reads the workspace except through the database's queries |

3. **The database lives in `lorecraft.project.database`**, with the witnesses (`DocumentText`, `SkillText`,
   `SkillResourceText`, `Undecodable`) and the contexts (`DatabaseDocumentContext`, `DatabaseSkillContext`).
   `lorecraft.checks` imports them from there and re-exports none of them.
4. **A rule still never reaches the database.** `lorecraft.rules` now sits above it, so the layers contract alone
   would allow the import; a forbidden contract in `pyproject.toml` refuses `lorecraft.rules` importing
   `lorecraft.project.database`. A rule reads only the context it is handed.

## Consequences

- The layers contract is unchanged: `project` gains no import from above, and every dependency of the database
  points downward.
- `lorecraft.project` now caches values derived from a snapshot. The cache is bounded by one database, so a value
  it holds still never outlives its snapshot, as [adr-005](adr-005-incremental.md) requires.
- `module-lorecraft-project` and `module-lorecraft-checks` move the queries, the witnesses, the carry-over rule and
  the context implementations from the second to the first.
- What stays true: every value derived from the snapshot is a query on the database
  ([adr-004](adr-004-database.md)), a check and a rule are pure, and a rule's result is never cached.
- adr-001 keeps `status: accepted`. The ADR specification defines supersession of a whole record only, and the
  roles this record leaves untouched must keep binding code, so the partial relation is carried by the callouts
  and the References entries alone: a deliberate reading of the specification, not a gap in following it.

## Checklist

Before committing code, verify:

- [ ] A query, a decode witness or a database-backed context is added in `lorecraft.project.database`, never in
  `lorecraft.checks`
- [ ] Nothing in `lorecraft.project` decides whether a value breaks a rule
- [ ] Nothing in `lorecraft.project` caches a value derived from a snapshot outside a database, or for longer than
  its revision
- [ ] Nothing in `lorecraft.checks` memoizes a value derived from the snapshot
- [ ] No module of `lorecraft.rules` imports `lorecraft.project.database`

## References

- [#410](https://github.com/LNSD/lorecraft/issues/410) - Source: The owner's decision to move the database into
  `lorecraft.project`
- [adr-001-snapshot-model](adr-001-snapshot-model.md) - Supersedes: The Derivation and Analysis rows of the role
  table
- [adr-004-database](adr-004-database.md) - Foundation: Revisions, the view and the queries
- [adr-005-incremental](adr-005-incremental.md) - Related: Carry-over and the store, the only caching across
  revisions
- [adr-011-rules-engine](adr-011-rules-engine.md) - Related: Where the engine's code lives
- [module-lorecraft-project](../code/module-lorecraft-project.md) - Leads to: The Derivation package's rules
- [module-lorecraft-checks](../code/module-lorecraft-checks.md) - Leads to: The Analysis package's rules
