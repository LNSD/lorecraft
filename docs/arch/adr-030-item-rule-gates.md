---
name: "adr-030-item-rule-gates"
description: "Item rules declare the kinds they judge and the gate that governs each kind, so the runner and rule table dispatch from one explicit contract."
type: "adr"
status: "proposed"
---

# Item Rule Gates

> [!NOTE]
> Proposed to supersede in part [adr-011](adr-011-rules-engine.md): the item rule bases and their implicit
> applicability in “A Subject's Facts Are the Query's,” and the corresponding item partitions and facet indexes in
> “Overview”; and [adr-026](adr-026-rule-owned-queries.md): decision 1's queried item bases and its matching item
> applicability statements in Consequences. Those records stay binding until this one is accepted.

## Context

The rules engine has several queried item bases with the same query and judgement shape. Their inheritance encodes
which items they judge and what must govern an item before judgement. The runner reconstructs those declarations with
`issubclass` checks, a facet lookup, and exceptions for the Agent Skills floor and a loaded skills corpus layer.
`RuleTable` repeats the class hierarchy to fill per-base partitions and facet indexes. A rule that applies to more
than one kind may use either a document-and-skill base or a frontmatter base, so applicability is split across
different vocabulary and inheritance paths.

This implicit contract makes adding or moving a rule a coordinated change to the base hierarchy, runner and table.
The Agent Skills schema floor is also a schema registry fact, but its special case is currently hidden in runner
control flow. The design needs to state applicability in rule data, retain the typed query-to-facts contract, and
keep layout subjects separate because their primitives and query subjects differ from item queries.

## Decision

1. **Item rules declare a gate for each item kind they judge.** Define a closed gate union with three immutable
   values:

   ```python
   @dataclass(frozen=True, slots=True)
   class BySpec:
       facet: Facet
       requires_loaded_layer: bool = False

   @dataclass(frozen=True, slots=True)
   class ByPackage:
       pass

   @dataclass(frozen=True, slots=True)
   class BySchema:
       schema: SchemaReference

   type Gate = BySpec | ByPackage | BySchema
   ```

   `BySpec(facet, requires_loaded_layer=False)` identifies the facet a rule reads from specifications. The runner
   uses it to select the item bucket and to report `ungoverned` coverage when that facet is inactive. When true on a
   skill-entry gate, `requires_loaded_layer` also requires loaded, successful skills-corpus governance before the
   rule is eligible; document-and-skill corpus rules set it. `ByPackage()` means the package governs the item kind
   without a per-item structure declaration. `BySchema(schema)` means the named schema is registered and therefore
   governs the item for this rule. These gates do not alter a rule's query or judgement.

2. **One queried item base owns the declaration.** Every item rule derives from `QueriedItemRule[Facts]`, which keeps
   the typed `query() -> ItemQuery[Facts]` and `judge(facts)` contract and declares a class-level mapping
   `GATES: Mapping[ItemKind, Gate]`. `ItemQuery[Facts]` is the query over `Primitives` that returns `Facts`; the
   shared `Query[P, Facts]` type names the primitive facet explicitly. A missing kind means the rule never judges
   that kind. Each rule writes its full mapping explicitly; no preset base encodes a default or preserves the old
   item-base names. A rule applying to both documents and skill entries declares both keys, even when they use the
   same gate.

   The mapping can express the existing cases directly: a document rule governed by facet `f` declares
   `{DOCUMENT: BySpec(f)}`; a skill rule declares `{SKILL_ENTRY: ByPackage()}`; and a rule shared by documents and
   skill entries declares a gate for each. A Markdown rule uses `BySpec(STRUCTURE)` for documents and package gates
   for skill entries and skill resources. A frontmatter rule uses `BySpec(FRONTMATTER)` for documents and skill
   entries, except `name_mismatch`, whose skill-entry gate is `BySchema` of the registered Agent Skills floor
   `SchemaReference`. When the floor is opted out, the frontmatter facet remains a coverage gate on skill entries
   and is reported as `ungoverned`; the rules do not judge that inactive facet. This is a vocabulary for
   applicability, not a central list of which rules exist.

3. **Schema-backed eligibility is explicit.** A rule whose applicability depends on a registered schema uses
   `BySchema` for that kind. In particular, the Agent Skills floor is represented by the registered
   `SchemaReference` used by the name-mismatch rule; there is no runner exception or synthetic governance facet for
   it. If a schema is not registered, the gate does not admit the rule. Schema registration and resolution remain
   governed by the schema registry design in ADR-028.

4. **The runner has one item eligibility predicate.** `judges(rule, descriptor, governance, model)` looks up the
   descriptor's kind in `rule.GATES` and evaluates the gate: a package gate admits the item, a schema gate requires
   the schema to be registered in the model, and a spec gate identifies the facet whose coverage the runner tracks.
   For a skill-entry `BySpec` gate whose `requires_loaded_layer` field is true, the predicate also requires loaded
   skills-corpus governance with no failed layer. This field carries today's loaded-corpus and failed-layer
   condition for document-and-skill corpus rules without a base-specific branch, and does not require a structure
   file. Other skill-entry spec gates, including frontmatter, do not inherit that restriction. The match is
   exhaustive over `Gate` and closes with `assert_never`. A missing mapping entry returns false. The runner has no
   `governing_facet` helper, `ItemQueriedRule` union, base-specific branch or Agent Skills floor exception.

   Eligibility and coverage remain distinct. When an applicable `BySpec` gate names a facet absent from the
   descriptor's active facets, the runner records `ungoverned` coverage and does not judge it. This includes skill
   frontmatter when the built-in schema is opted out and no repository schema activates the facet. A rule whose kind
   is absent from `GATES`, a schema gate whose schema is unregistered, or a document-and-skill corpus rule on a skill
   entry without loaded skills governance is skipped silently. The runner therefore reads the gate both to select
   rules and to record coverage; `judges` does not replace that behavior.

   The runner still owns evaluation order, decoding, diagnostics and rule judgement.

5. **The table indexes items from declared gates.** `RuleTable` partitions rules into item, symlink and corpus
   directory groups, with one item index keyed by `(ItemKind, Facet)` where facet-specific selection is needed.
   Building the table reads `GATES`, rather than branching on a rule's base class. It keeps enabled rules and their
   severity and preserves registry order. Layout groups remain typed separately and do not acquire item gates.

6. **An item rule cannot register without applicability.** Registry loading rejects an item rule whose `GATES` is
   empty, at package load time, with the same boundary discipline used for a missing `GOVERNED_BY` declaration.
   This prevents a structurally valid but unreachable rule from silently entering the registry. The registry does
   not infer a gate from a class or silently supply one.

7. **Layout rule bases stay separate.** `QueriedSymlinkRule` and `QueriedCorpusDirectoryRule` keep their own
   subject-specific query types, `Query[SymlinkPrimitives, Facts]` and
   `Query[CorpusDirectoryPrimitives, Facts]`. A layout subject is not an item kind, and combining those bases with
   `QueriedItemRule` would weaken the per-subject typing required by ADR-027 and ADR-029.

## Consequences

- A rule's applicability can be read from its declaration, while its query remains typed by its facts. Adding an
  item kind to a rule requires an explicit gate instead of a new inheritance path or runner branch.
- The runner and table derive eligibility and indexes from the same mapping. This removes their duplicated
  interpretation of the item-base hierarchy and makes missing gate cases visible at registry load.
- Package, structure-file and schema governance remain distinct. Schema-backed cases follow registry presence,
  while package-governed kinds do not need artificial facets.
- Existing judgement behavior and rule-case diagnostics remain the compatibility boundary. This decision changes
  how eligibility is declared and selected, not rule queries, findings, severity, or diagnostic output.
- Layout rules retain their distinct types and dispatch because their subjects do not share item primitives.

## Alternatives Considered

- **Keep the existing bases and add attributes to each.** This would leave inheritance as a second applicability
  vocabulary, so callers could disagree about which declaration controls dispatch.
- **Use separate per-kind booleans or facet fields.** This duplicates combinations across bases and cannot express
  registry-backed schema eligibility without another special case.
- **Fold layout subjects into the item base.** Layout records have different primitive contracts and are not item
  kinds; a common base would erase the query-to-subject typing the engine relies on.

## References

- [adr-011](adr-011-rules-engine.md) - Foundation: Runner orchestration, rule tables and item governance
- [adr-026](adr-026-rule-owned-queries.md) - Foundation: Typed rule queries and judgements
- [adr-028](adr-028-schema-registry.md) - Foundation: Registered schema references and resolution
- [adr-027](adr-027-subject-keyed-queries.md) - Constraint: Subject-specific query types
- [adr-029](adr-029-unified-query-engine.md) - Constraint: Typed dispatch across subjects
- [adr-022](adr-022-skills-governance.md) - Foundation: Agent Skills floor governance
