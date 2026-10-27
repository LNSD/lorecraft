---
name: "adr-030-item-rule-gates"
description: "Item rules declare the item types they judge and the spec part condition that gates each item type. Load when changing item-rule applicability, spec governance parts, or their coverage."
type: "adr"
status: "accepted"
---

# Item Rule Applicability

> [!NOTE]
> Supersedes in part [adr-009](adr-009-rules.md): the passage requiring document rules to declare
> `GOVERNED_BY` and treating skills/layout rules as declaring none; [adr-011](adr-011-rules-engine.md): item
> applicability in “A Subject's Facts Are the Query's” and “A Subject's Status Comes Before Any Rule,” plus the
> item partitions and facet indexes in “The Runner”; and [adr-029](adr-029-unified-query-engine.md): decision 1's
> queried item bases and their matching item-applicability statements in Consequences. Those records stay binding
> outside these passages.

## Context

The rules engine has several queried item bases with the same query and judgement shape. Their inheritance encodes
which item types they judge and what must govern an item before judgement. The runner reconstructs those declarations with
`issubclass` checks, a spec-part lookup, and exceptions for the Agent Skills floor and a loaded skills corpus
layer. `RuleTable` repeats the class hierarchy to fill per-base partitions and spec-part indexes. A rule that
applies to more than one item type may use either a document-and-skill base or a frontmatter base, so applicability is
split across different vocabulary and inheritance paths.

This implicit contract makes adding or moving a rule a coordinated change to the base hierarchy, runner and table.
The Agent Skills schema floor is also a schema registry fact, but its special case is currently hidden in runner
control flow. The design needs to state applicability in rule data, retain the typed query-to-facts contract, and
keep layout subjects separate because their primitives and query subjects differ from item queries.

## Decision

1. **Item rules declare a gate for each item type they judge.** Define one `SpecPart` enum in `project`,
   replacing `Facet` and `ItemFacet`, with `FRONTMATTER`, `STRUCTURE`, `OUTLINE` and `BUDGET`; drop `MARKDOWN`.
   Their serialized values (`frontmatter`, `structure`, `outline`, `budget`) and coverage labels stay unchanged.
   Define a closed gate union with two immutable values:

   ```python
   @dataclass(frozen=True, slots=True)
   class WhenSpec:
       part: SpecPart

   @dataclass(frozen=True, slots=True)
   class Always:
       pass

   type Gate = WhenSpec | Always
   ```

   `WhenSpec(part)` identifies the part a rule reads from specs. The runner uses it to select the item bucket
   and to report `ungoverned` coverage when a loaded layer does not state that part. `Always()` means the item type
   listed in `APPLIES_TO` is admitted independently of a per-item spec declaration. This replaces `ByPackage()`,
   whose name suggested a repository-wide scope even though it only admitted the item type explicitly mapped by the rule.
   These gates do not alter a rule's query or judgement.

2. **One queried item base owns the declaration.** Every item rule derives from `QueriedItemRule[Facts]`, which keeps
   the typed `query() -> ItemQuery[Facts]` and `judge(facts)` contract and declares a class-level mapping
   `APPLIES_TO: Mapping[ItemType, Gate]`. `ItemQuery[Facts]` is the query over `ItemPrimitives` that returns
   `Facts`; the shared `Query[P, Facts]` type names the primitive group explicitly. A missing item type means the rule never
   judges that item type. Each rule writes its full mapping explicitly; no preset base encodes a default or preserves the old
   item-base names. A rule applying to both documents and skills declares both keys, even when they use the
   same gate.

   The mapping expresses applicability directly across item types:
   - An ordinary document rule governed by part `p` declares `{DOCUMENT: WhenSpec(p)}`.
   - Spec items in `docs/__meta__/` are governed by the reserved `meta` corpus and declare the same gates as document items.
   - Markdown syntax link checks (`broken_link`, `broken_fragment`, `absolute_link`) use `Always()` for all item types, documents and skills included.
   - Link containment (`escaping_link`) uses `Always()` for `DOCUMENT`, `SPEC`, `SKILL_ENTRYPOINT`, and `SKILL_RESOURCE`, enforcing containment as an unconditional invariant.
   - Corpus naming convention checks (`missing_base_link`, `extension_link`, `mutual_link`) remain `WhenSpec(STRUCTURE)` for documents.
   - Frontmatter rules, including `name_mismatch` (per ADR-028 Decision 16), declare `WhenSpec(FRONTMATTER)` for documents, specs, and skills.
   - Declarative structure budget rules declare spec gates: `too_many_lines` declares `{DOCUMENT: WhenSpec(BUDGET), SPEC: WhenSpec(BUDGET), SKILL_ENTRYPOINT: WhenSpec(BUDGET)}`, and builtin tool constraints (`allowed_tools_too_long`, `malformed_allowed_tools`) declare `{SKILL_ENTRYPOINT: WhenSpec(FRONTMATTER)}`.
   - When the builtin floor is opted out and no repository layer states the part, the corresponding spec part is reported under coverage as `ungoverned` and the gated rules do not judge the item.

3. **Governance follows loaded layers.** `governed_parts` contains only the parts stated by loaded layers (builtin floor and repository layers), for every
   item type; no part is forced active. A skill rule
   gated by a part uses plain `WhenSpec(part)`, just as a document rule does: an active layer stating the part is the
   condition for judging. Skill checks independent of a spec part use `Always()`. `requires_loaded_layer` is
   removed. When a skills layer fails, skills follow the mode's skip policy in
   `engine/skip.py`, rather than handling failed-layer state in `judges`.

   Specs in `docs/__meta__/` are governed by the reserved `meta` corpus: `meta.spec.json` is the corpus meta spec,
   and `meta-<corpus>.spec.json` is the namespace meta spec for specs named `<corpus>` or `<corpus>-*`.
   `SpecOrigin.corpus` records the specification's subject category, while `ItemDescriptor.governance_corpus` is
   `'meta'`. Rules applied to `SPEC` items declare the same gates as document rules.

   When any governing layer fails to load, Lorecraft applies a uniform partial check policy across all item types:
   the failed layer suppresses every `WhenSpec` gate, while `Always` gates still run. The
   suppressed spec parts are reported under coverage, rather than skipping the subject entirely.

   When the builtin Agent Skills floor is active, skills are governed for `FRONTMATTER` and `BUDGET`.
   A skill with no repository skills-corpus layer is reported as `ungoverned` for `STRUCTURE` and `OUTLINE`
   when enabled rules read those parts. When the builtin floor is opted out via `--no-agent-skills-spec` and no repository
   skills layer provides them, `FRONTMATTER` and `BUDGET` are also reported as `ungoverned`. Coverage therefore exposes
   missing governance instead of silently skipping the entry.

4. **Schema and budget eligibility is governed by SpecPart.** Applicable schema and structure constraints enter
   through the loaded layers and are queried via `SpecPart` gates (`WhenSpec(FRONTMATTER)` and `WhenSpec(BUDGET)`).
   `WhenSchema` is retired: the Agent Skills floor is no longer a special runner or schema-reference case, but a builtin
   spec layer whose presence activates `FRONTMATTER` and `BUDGET` governance. If a part is not governed across loaded
   layers, the gate does not admit the rule and coverage reports the part as `ungoverned`. Schema registration and resolution
   remain governed by the schema registry design in ADR-028.

5. **The runner has one item eligibility predicate.** `judges(rule, descriptor, governance, model)` looks up the
   descriptor's type in `rule.APPLIES_TO` and evaluates the gate: an `Always` gate admits the mapped item type, and a
   `WhenSpec` gate identifies the part whose presence in `descriptor.governed_parts` admits the rule and whose absence
   the runner tracks as `ungoverned` coverage. No gate forces a skills-corpus layer to be loaded; failed-layer handling
   follows the mode's skip policy. The match is exhaustive over `Gate` (`WhenSpec | Always`) and closes with `assert_never`.
   A missing mapping entry returns false. The runner has no `governing_facet` helper, `ItemQueriedRule` union, base-specific
   branch or Agent Skills floor exception.

   Eligibility and coverage remain distinct. When an applicable `WhenSpec` gate names a part absent from the
   descriptor's `governed_parts`, the runner records `ungoverned` coverage and does not judge it. This includes skill
   frontmatter and budget when the builtin floor is opted out and no repository layer activates those parts. A rule whose
   item type is absent from `APPLIES_TO` is skipped silently. The runner reads the gate both to select rules and to record
   coverage; `judges` does not replace that behavior.

   The runner still owns evaluation order, decoding, diagnostics and rule judgement.

6. **The table indexes items from declared gates.** `RuleTable` partitions rules into item, symlink and corpus
   directory groups, with one item index keyed by `(ItemType, SpecPart)` where part-specific selection is
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
   with `QueriedItemRule` would weaken the per-subject typing required by ADR-029.

## Consequences

- A rule's applicability can be read from its declaration, while its query remains typed by its facts. Adding an
  item type to a rule requires an explicit gate instead of a new inheritance path or runner branch.
- The runner and table derive eligibility and indexes from the same mapping. This removes their duplicated
  interpretation of the item-base hierarchy and makes missing gate cases visible at registry load.
- `WhenSpec` and `Always` form a closed, two-member gate union. `WhenSchema` is retired because the builtin
  Agent Skills floor is an active spec layer whose frontmatter and budget constraints gate on `WhenSpec`,
  and `Always` admits only the item types named in `APPLIES_TO` without requiring a per-item spec declaration.
- Specs in `docs/__meta__/` are governed by the reserved `meta` corpus; `meta.spec.json` and namespace layers
  `meta-<corpus>.spec.json` apply to spec items with the same gate semantics as corpus documents.
- Markdown syntax link checks run for all item types, ensuring link integrity across documents and
  skills without requiring structure files.
- Link containment (`escaping_link`) remains an unconditional `Always` invariant across documents, specs,
  skill entrypoints, and skill resources.
- A failed governing layer applies a uniform partial check policy across all item types: spec gates are
  suppressed and reported under coverage while `Always` gates still execute.
- When the builtin floor is active, skills are governed for `FRONTMATTER` and `BUDGET`; `STRUCTURE` and `OUTLINE`
  appear as ungoverned when no repository skills layer states them. When the floor is opted out via
  `--no-agent-skills-spec`, `FRONTMATTER` and `BUDGET` also appear in coverage as ungoverned, making missing governance
  transparent instead of mistaking silence for coverage.
- Existing judgement behavior and rule-case diagnostics remain the compatibility boundary. Moving formerly
  hardcoded floor checks (`too_many_lines`, tool constraints) into declarative spec rules preserves their
  diagnostic findings, warning severity, and attribution.
- Layout rules retain their distinct types and dispatch because their subjects do not share item primitives.

## Alternatives Considered

- **Keep the existing bases and add attributes to each.** This would leave inheritance as a second applicability
  vocabulary, so callers could disagree about which declaration controls dispatch.
- **Use separate per-item-type booleans or part fields.** This duplicates combinations across bases and cannot express
  registry-backed schema eligibility without another special case.
- **Add a `BySkillsCorpus(part)` gate.** This would preserve the current silent skip for skills without a
  loaded skills corpus, but it would make skills-corpus presence a separate eligibility concept. Coverage is meant
  to expose ungoverned parts, so the simpler `WhenSpec(part)` gate is preferred.
- **Retain `WhenSchema` alongside `WhenSpec`.** Rejected: since the floor supplies a builtin spec layer
  with both frontmatter schema and line limits, gating on `WhenSpec(FRONTMATTER)` and `WhenSpec(BUDGET)`
  unifies skill and document governance and leaves no consumers for `WhenSchema`.
- **Fold layout subjects into the item base.** Layout records have different primitive contracts and are not item
  types; a common base would erase the query-to-subject typing the engine relies on.

## Checklist

- [ ] Item rules declare applicability via `APPLIES_TO: Mapping[ItemType, Gate]` using `WhenSpec` or `Always`
- [ ] `WhenSchema` is retired, leaving `Gate = WhenSpec | Always`
- [ ] `name_mismatch`, `allowed_tools_too_long`, and `malformed_allowed_tools` gate on `WhenSpec(FRONTMATTER)`
- [ ] `too_many_lines` gates on `WhenSpec(BUDGET)` for documents, specs, and skill entrypoints
- [ ] `escaping_link` gates on `Always()` for documents, specs, skill entrypoints, and skill resources
- [ ] Failed governing layers suppress `WhenSpec` gates while `Always` gates continue to run
- [ ] When the builtin floor is active, skills declare `FRONTMATTER` and `BUDGET` governance
- [ ] When the builtin floor is opted out and no repository layer provides them, `FRONTMATTER` and `BUDGET` are reported as ungoverned under coverage
- [ ] Runner and rule table derive item eligibility and indexes directly from `APPLIES_TO` without runner exceptions

## References

- [adr-009](adr-009-rules.md) - Supersedes in part: `GOVERNED_BY` declaration and former `ByPackage` passage
- [adr-011](adr-011-rules-engine.md) - Supersedes in part: Item applicability, item partitions and facet indexes;
  foundation: runner orchestration and rule tables
- [adr-028](adr-028-schema-registry.md) - Foundation: Registered schema references and resolution
- [adr-029](adr-029-unified-query-engine.md) - Supersedes in part: Decision 1's queried item bases; constraint:
  subject-specific query types and typed dispatch
- [adr-022](adr-022-skills-governance.md) - Foundation: Agent Skills floor governance
