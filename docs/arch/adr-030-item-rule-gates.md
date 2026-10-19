---
name: "adr-030-item-rule-gates"
description: "Item rules declare the item types they judge and the meta-spec part or schema condition that gates each item type. Load when changing item-rule applicability, meta-spec governance parts, or their coverage."
type: "adr"
status: "proposed"
---

# Item Rule Applicability

> [!NOTE]
> Proposed to supersede in part [adr-009](adr-009-rules.md): the passage requiring document rules to declare
> `GOVERNED_BY` and treating skills/layout rules as declaring none; [adr-011](adr-011-rules-engine.md): item
> applicability in “A Subject's Facts Are the Query's” and “A Subject's Status Comes Before Any Rule,” plus the
> item partitions and facet indexes in “The Runner”; and [adr-026](adr-026-rule-owned-queries.md): decision 1's
> queried item bases and their matching item-applicability statements in Consequences. Those records stay binding
> outside these passages, and until this one is accepted.

## Context

The rules engine has several queried item bases with the same query and judgement shape. Their inheritance encodes
which item types they judge and what must govern an item before judgement. The runner reconstructs those declarations with
`issubclass` checks, a meta-spec-part lookup, and exceptions for the Agent Skills floor and a loaded skills corpus
layer. `RuleTable` repeats the class hierarchy to fill per-base partitions and meta-spec-part indexes. A rule that
applies to more than one item type may use either a document-and-skill base or a frontmatter base, so applicability is
split across different vocabulary and inheritance paths.

This implicit contract makes adding or moving a rule a coordinated change to the base hierarchy, runner and table.
The Agent Skills schema floor is also a schema registry fact, but its special case is currently hidden in runner
control flow. The design needs to state applicability in rule data, retain the typed query-to-facts contract, and
keep layout subjects separate because their primitives and query subjects differ from item queries.

## Decision

1. **Item rules declare a gate for each item type they judge.** Define one `MetaSpecPart` enum in `project`,
   replacing `Facet` and `ItemFacet`, with `FRONTMATTER`, `STRUCTURE`, `OUTLINE` and `BUDGET`; drop `MARKDOWN`.
   Their serialized values (`frontmatter`, `structure`, `outline`, `budget`) and coverage labels stay unchanged.
   Define a closed gate union with three immutable values:

   ```python
   @dataclass(frozen=True, slots=True)
   class WhenMetaSpec:
       part: MetaSpecPart

   @dataclass(frozen=True, slots=True)
   class Always:
       pass

   @dataclass(frozen=True, slots=True)
   class WhenSchema:
       schema: SchemaReference

   type Gate = WhenMetaSpec | Always | WhenSchema
   ```

   `WhenMetaSpec(part)` identifies the part a rule reads from meta specs. The runner uses it to select the item bucket
   and to report `ungoverned` coverage when a loaded layer does not state that part. `Always()` means the item type
   listed in `APPLIES_TO` is admitted independently of a per-item meta-spec declaration. This replaces `ByPackage()`,
   whose name suggested a repository-wide scope even though it only admitted the item type explicitly mapped by the rule.
   `WhenSchema(schema)` means the named schema is registered and therefore governs the item for this rule. These
   gates do not alter a rule's query or judgement.

2. **One queried item base owns the declaration.** Every item rule derives from `QueriedItemRule[Facts]`, which keeps
   the typed `query() -> ItemQuery[Facts]` and `judge(facts)` contract and declares a class-level mapping
   `APPLIES_TO: Mapping[ItemType, Gate]`. `ItemQuery[Facts]` is the query over `ItemPrimitives` that returns
   `Facts`; the shared `Query[P, Facts]` type names the primitive group explicitly. A missing item type means the rule never
   judges that item type. Each rule writes its full mapping explicitly; no preset base encodes a default or preserves the old
   item-base names. A rule applying to both documents and skills declares both keys, even when they use the
   same gate.

   The mapping can express the existing cases directly: an ordinary document rule governed by part `p` declares
   `{DOCUMENT: WhenMetaSpec(p)}`; a skill check independent of meta-spec parts declares
   `{SKILL_ENTRYPOINT: Always()}`; and a rule shared by documents and skills declares a gate for each. A Markdown rule uses `WhenMetaSpec(STRUCTURE)` for ordinary
   documents and `Always()` for `SPECIFICATION`, `SKILL` and `SKILL_RESOURCE`. A frontmatter rule uses
   `WhenMetaSpec(FRONTMATTER)` for documents and skills, except `name_mismatch`, whose skill gate is
   `WhenSchema` of the registered Agent Skills floor `SchemaReference`. When the floor is opted out, the
   frontmatter part remains a coverage gate on skills and is reported as `ungoverned`; the rules do not judge that
   inactive part. This is a vocabulary for applicability, not a central list of which rules exist.

3. **Governance follows loaded layers.** `governed_parts` contains only the parts stated by loaded layers, for every
   item type; no part is forced active. Rules applied to `SPECIFICATION` items use `Always()`. A skill rule
   gated by a part uses plain `WhenMetaSpec(part)`, just as a document rule does: a skills layer stating the part is the
   condition for judging. Skill checks independent of a meta-spec part use `Always()`. `requires_loaded_layer` is
   removed. When a skills layer fails, skills follow the mode's skip policy in
   `engine/skip.py`, rather than handling failed-layer state in `judges`.

   A skill with no skills-corpus layer is reported as `ungoverned` for `STRUCTURE`, `OUTLINE` and `BUDGET`
   when enabled rules read those parts. Coverage therefore exposes missing governance instead of silently skipping
   the entry. This is the recommended behavior because coverage describes what is ungoverned, as it does for
   documents. The alternative, a separate skills-corpus gate, would preserve today's silent skip but introduce a
   fourth gate solely for the skills-corpus condition.

4. **Schema-backed eligibility is explicit.** A rule whose applicability depends on a registered schema uses
   `WhenSchema` for that item type. In particular, the Agent Skills floor is represented by the registered
   `SchemaReference` used by the name-mismatch rule; there is no runner exception or synthetic governance part for
   it. If a schema is not registered, the gate does not admit the rule. Schema registration and resolution remain
   governed by the schema registry design in ADR-028.

5. **The runner has one item eligibility predicate.** `judges(rule, descriptor, governance, model)` looks up the
   descriptor's type in `rule.APPLIES_TO` and evaluates the gate: an `Always` gate admits the mapped item type, a schema gate requires the schema to be registered in the model, and a meta-spec gate identifies the part whose coverage the runner
   tracks. No gate forces a skills-corpus layer to be loaded; failed-layer handling follows the mode's skip policy.
   The match is exhaustive over `Gate` and closes with `assert_never`. A missing mapping entry returns false. The runner has no `governing_facet` helper, `ItemQueriedRule` union, base-specific branch or Agent Skills floor exception.

   Eligibility and coverage remain distinct. When an applicable `WhenMetaSpec` gate names a part absent from the
   descriptor's `governed_parts`, the runner records `ungoverned` coverage and does not judge it. This includes skill
   frontmatter when the built-in schema is opted out and no repository schema activates the part. A rule whose item type
   is absent from `APPLIES_TO` or a schema gate whose schema is unregistered is skipped silently. The runner reads the gate
   both to select rules and to record coverage; `judges` does not replace that behavior.

   The runner still owns evaluation order, decoding, diagnostics and rule judgement.

6. **The table indexes items from declared gates.** `RuleTable` partitions rules into item, symlink and corpus
   directory groups, with one item index keyed by `(ItemType, MetaSpecPart)` where part-specific selection is
   needed.
   Building the table reads `APPLIES_TO`, rather than branching on a rule's base class. It keeps enabled rules and their
   severity and preserves registry order. Layout groups remain typed separately and do not acquire item gates.

7. **An item rule cannot register without applicability.** Registry loading rejects an item rule whose `APPLIES_TO` is
   empty, when the registry loads, with the same boundary discipline used for an item rule without a gate.
   This prevents a structurally valid but unreachable rule from silently entering the registry. The registry does
   not infer a gate from a class or silently supply one.

8. **Layout rules keep subject-specific queried bases.** `QueriedSymlinkRule` and
   `QueriedCorpusDirectoryRule` directly provide the rule bases, with query types `Query[SymlinkPrimitives, Facts]`
   and `Query[CorpusDirectoryPrimitives, Facts]`. A layout subject is not an item type, and combining those bases
   with `QueriedItemRule` would weaken the per-subject typing required by ADR-027 and ADR-029.

## Consequences

- A rule's applicability can be read from its declaration, while its query remains typed by its facts. Adding an
  item type to a rule requires an explicit gate instead of a new inheritance path or runner branch.
- The runner and table derive eligibility and indexes from the same mapping. This removes their duplicated
  interpretation of the item-base hierarchy and makes missing gate cases visible at registry load.
- `WhenMetaSpec`, `Always`, and `WhenSchema` remain distinct. Schema-backed cases follow registry presence, while
  `Always` admits only the item types named in `APPLIES_TO` without requiring a per-item meta-spec declaration.
- Skills without a skills-corpus layer appear in coverage as ungoverned for the parts enabled rules need;
  readers can see missing governance instead of mistaking silence for coverage.
- Existing judgement behavior and rule-case diagnostics remain the compatibility boundary. This decision changes
  how eligibility is declared and selected, not rule queries, findings, severity, or diagnostic output.
- Layout rules retain their distinct types and dispatch because their subjects do not share item primitives.

## Alternatives Considered

- **Keep the existing bases and add attributes to each.** This would leave inheritance as a second applicability
  vocabulary, so callers could disagree about which declaration controls dispatch.
- **Use separate per-item-type booleans or part fields.** This duplicates combinations across bases and cannot express
  registry-backed schema eligibility without another special case.
- **Add a `BySkillsCorpus(part)` gate.** This would preserve the current silent skip for skills without a
  loaded skills corpus, but it would make skills-corpus presence a separate eligibility concept. Coverage is meant
  to expose ungoverned parts, so the simpler `WhenMetaSpec(part)` gate is preferred.
- **Fold layout subjects into the item base.** Layout records have different primitive contracts and are not item
  types; a common base would erase the query-to-subject typing the engine relies on.

## References

- [adr-009](adr-009-rules.md) - Supersedes in part: `GOVERNED_BY` declaration and former `ByPackage` passage
- [adr-011](adr-011-rules-engine.md) - Foundation: Runner orchestration, rule tables and item governance
- [adr-026](adr-026-rule-owned-queries.md) - Foundation: Typed rule queries and judgements
- [adr-028](adr-028-schema-registry.md) - Foundation: Registered schema references and resolution
- [adr-027](adr-027-subject-keyed-queries.md) - Constraint: Subject-specific query types
- [adr-029](adr-029-unified-query-engine.md) - Constraint: Typed dispatch across subjects
- [adr-022](adr-022-skills-governance.md) - Foundation: Agent Skills floor governance
