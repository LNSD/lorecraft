---
name: "adr-023-governed-items"
description: "Unify corpus documents, skills and skill resources behind one governed-item reference and model-resolved descriptor across the project model, database and rules engine. Load when changing document or skill references, governance resolution, database per-file or analysis queries, or runner subject dispatch"
type: "adr"
status: "accepted"
---

# Unified Governed-Item Reference and Pipeline

> [!NOTE]
> Supersedes in part [adr-003](adr-003-project-model.md), [adr-011](adr-011-rules-engine.md) and
> [adr-015](adr-015-database.md): their separate document, skill and resource reference types, decode witnesses,
> per-kind database query families, per-kind runner branches, and document-only governance and failed-layer skipping.
> Declared scope versus captured content, identity versus location, lazy database queries, and levels after detection
> stay in force in all three records.

## Context

[prd-020](prd-020-skills-corpus.md) brings skill entrypoints into the meta spec model through the reserved
`skills` corpus (`FR-001` through `FR-007`, `FR-009` through `FR-011`, `FR-018`, `NFR-001`), and
[adr-022](adr-022-skills-governance.md) settles how `skills` layers, the built-in schema and bounded contradiction
detection work.

In the current architecture, documents under `docs/`, skill entrypoints (`SKILL.md`) and Markdown resources inside
skills travel through three parallel representations above the project model:

- Separate reference types identify corpus documents by corpus and filename stem, skills by their listed directory name, and skill resources by owning skill and skill-relative path.
- Governance resolution accepts only corpus document references.
- The database maintains separate decode witnesses, caches and query methods for decoding, frontmatter parsing,
  Markdown parsing, line counting, schema validation and relative-link target lookup across the three kinds.
- Context protocols, the rule table, the runner and subject reports branch on whether a Markdown subject is a document,
  a skill or a skill resource.

Extending that split to support `skills` repository layers (`FR-005`) and later governed skill resources would duplicate
governance lookup, failed-layer skipping, meta spec part gating and coverage reporting across parallel pipelines.

## Decision

### One Governed-Item Reference and Model-Resolved Descriptor

Every governed Markdown subject—a document in a `docs/` corpus, a meta spec in `docs/__meta__/`, a skill's `SKILL.md`,
or a Markdown resource inside a skill—is identified above the project model by one owned reference type and paired
with a descriptor resolved by the project model.

The reference carries the item's logical identity where it is listed, never its resolved target path
([adr-003](adr-003-project-model.md)). Retargeting a symlink changes the resolved location in the descriptor while
leaving the reference unchanged.

The descriptor records the facts that differ by origin so no layer above the project model branches on how the item
was discovered:

- **Logical reference and report path:** the root-relative path reported in diagnostics and coverage (`FR-010`,
  `NFR-001`).
- **Resolved file location:** the snapshot path that decoding reads ([adr-003](adr-003-project-model.md)).
- **Link resolution base and climb bound:** relative Markdown links resolve from the document's own directory for a
  corpus document or meta spec, and from the skill root for a skill's `SKILL.md` or resource. The climb bound is the
  repository root for documents and meta specs, and the skill root for skills and resources; crossing it is the
  `LINK004` condition described by [adr-010](adr-010-diagnostics.md) ([adr-011](adr-011-rules-engine.md)).
- **Frontmatter owner metadata:** the expected `name` value, whether it comes from a document stem or a listed skill
  directory, any resolved symlink target needed for diagnostic notes, and the governing schema provenance required to
  preserve existing frontmatter findings (`FR-013`).
- **Governance target and governed meta spec parts:** the corpus and aspect name used to resolve governing layers, together with the meta spec parts that govern the item (`FR-005`, `FR-014`).

Layout symlinks that leave the repository have no Markdown content and no corpus governance; they remain a separate
layout subject category ([adr-011](adr-011-rules-engine.md)).

### Origin Classification Stays Inside the Project Model

The project model is the only layer that classifies a Markdown item's origin:

- A corpus document derives its corpus and aspect name from its `docs/<corpus>/<name>.md` path.
- A meta spec in `docs/__meta__/` derives its subject corpus from its filename prefix and is governed by the reserved
  `meta` corpus.
- A skill derives its aspect name from its listed directory name in `.agents/skills/`. Its `Always` checks remain
  independent of the skill entrypoint's governance by the reserved `skills` corpus.
- A skill resource is discovered lazily through its skill's resource listing rather than by an eager workspace-wide
  walk when the model opens ([adr-003](adr-003-project-model.md), [adr-015](adr-015-database.md)). When listed, it
  yields the same common reference and descriptor shape as any other Markdown item.

Name-chain ordering and prefix matching are shared with the project model's meta spec and document hierarchy
derivation rather than reimplemented in the database, runner or rules.

### Hierarchical Governance for Meta Specs, Skills and Resources

The reserved `meta` corpus governs every meta spec in `docs/__meta__/`: `meta.spec.json` provides corpus governance
and `meta-<corpus>.spec.json` provides namespace governance. Meta spec rules declare the same gates as document rules.

The reserved `skills` corpus governs skill entrypoints. `Always` skill checks remain active independently of
that corpus governance. Skill resources remain outside meta-spec governance and have no corpus governance; they retain
`Always` link and syntax checks.

A Markdown resource inside a skill is not governed by meta specs or floor schemas. The model activates `Always` Markdown
checks only for resources; no skills-corpus schema or structure spec applies, leaving resource-specific rule models
open for future exploration.

### One Decode Witness, Query Family and Runner Pipeline

The database and rules engine consume the common reference and descriptor uniformly:

- **One decode boundary:** `Database` decodes any governed Markdown item through one query keyed by the common
  reference, reading the descriptor's resolved file location and returning one decode witness type or an undecodable
  marker ([adr-011](adr-011-rules-engine.md), [adr-015](adr-015-database.md)).
- **Unified per-file and cross-file queries:** frontmatter parsing, Markdown parsing, line counting, token counting and
  relative-link target resolution each have one query implementation taking the common decode witness and reading the
  descriptor's link base.
- **Unified governance and analysis queries:** `item_governance(ref)` resolves ordered layers for corpus documents and meta specs in `docs/__meta__/`, and for skill entrypoints through the
  reserved `skills` corpus; resources have no corpus governance. Schema validation and outline analysis read `item_governance(ref)` and the per-file queries, keeping their results whenever those inputs compare
  equal ([adr-015](adr-015-database.md)).
- **One content runner loop:** the engine decodes the item once, applies the uniform partial check policy whenever an
  active governing layer failed to load (suppressing `WhenMetaSpec` gates while running `Always` and `WhenSchema`
  checks), gates enabled rules by declared gates and governed parts, and produces one checked content report carrying
  diagnostics and ungoverned parts (`FR-005`, `FR-010`, `FR-018`).

### Refused Reads and Unchecked Documentation Symlinks

- **One refused-read report shape:** when a read of any Markdown item is refused, the engine reports
  `SkippedSubject(REFUSED_PATH)`. The command line renders each refused item read as `LC002` at the refused path,
  and marks the item as skipped with that cause in coverage.
- **An unchecked symlink under `docs/` is coverage:** until corpus-directory symlinks are followed, a symlinked
  corpus directory or document that is not checked is visible in coverage. It is not a diagnostic and does not add
  a separate engine condition.

### Diagnostic and Inspection Compatibility

The pipeline preserves the existing user-visible contract outside what [prd-020](prd-020-skills-corpus.md) requires,
except for the link-bound diagnostic and unchecked-symlink coverage decisions above:

- With no repository `skills` meta spec and the built-in schema enabled, skills and resources produce the
  exact diagnostics, notes, severity and sort order they produce today (`FR-013`).
- `lorecraft inspect` renders corpus documents and skills, without reporting corpus governance for skills.

## Consequences

- **One pipeline for every governed Markdown file.** New frontmatter, outline, budget or Markdown rules apply to corpus
  documents, skills and (when enabled) skill resources without adding per-kind database queries, context
  adapters or runner loops (`FR-005`, `FR-010`).
- **Broader initial refactor, smaller surface afterwards.** Replacing the three reference and witness families touches
  the project model, database, context protocols, runner and report types together, and removes the parallel query and
  dispatch code that would otherwise grow with `skills` governance.
- **Skill resources remain ungoverned by meta specs.** Skill resources share the unified reference and witness
  machinery, while remaining entirely outside meta-spec governance. Repository structure files, frontmatter schemas,
  and floor schemas do not govern skill resources; only `Always` link and syntax checks remain active. Any potential
  resource-specific governance model remains deferred for future exploration.
- **What stays true:** scope is declared rather than inferred from content ([adr-003](adr-003-project-model.md));
  logical identity is separate from resolved file location; the database opens with its model and computes per-file and
  analysis queries lazily ([adr-015](adr-015-database.md)); layers apply independently by conjunction
  ([adr-016](adr-016-specifications.md)); and levels apply after detection ([adr-011](adr-011-rules-engine.md)).

## Alternatives Considered

- **Keep the existing reference and runner split, and add repository governance only to `SkillRef` and `SkillContext`.**
  Smallest immediate diff for [prd-020](prd-020-skills-corpus.md). Rejected: it duplicates governance lookup,
  failed-layer skipping, outline/budget context methods and coverage reporting across documents and skills, and
  requires a second migration when skill resources gain governance.
- **Keep `DocumentRef`, `SkillRef` and `SkillResourceRef` behind a shared protocol.** Preserves per-origin construction
  types while normalizing consumer calls. Rejected: cache keys, witnesses and reports still require a cross-variant
  identity and descriptor contract, and keeping three reference types above the project model leaks origin
  classification past the boundary meant to encapsulate it.
- **Match governed skill resources by their own filename stems instead of their owning skill.** Lets a meta spec
  target a resource filename across skills. Rejected: a skill is a unit whose resources exist to support its entry, so
  the `skills` corpus establishes governance hierarchically from the containing skill.

## Checklist

Before committing code, verify:

- [ ] Above the project model, corpus documents, skills and skill resources use one governed-item reference type
  and one decode witness type
- [ ] The project model resolves each item's read location, report path, link base, frontmatter owner metadata,
  governance identity and governed meta spec parts once
- [ ] Logical identity stays separate from resolved symlink location for documents, skills and skill resources
  alike, and skill resource discovery remains lazy through the skill resource listing
- [ ] Skill resources remain outside meta-spec governance and have no corpus governance, retaining only package
  link and syntax checks; resource-specific governance models remain deferred for future exploration.
- [ ] The database provides one decode, per-file, analysis and link-target query family for governed Markdown items,
  with analyses depending on `item_governance(ref)` rather than the whole model
- [ ] The rules engine runs one content-item check loop that decodes once, applies failed-layer policy, gates rules by
  governed meta spec parts and records ungoverned parts uniformly
- [ ] Relative links resolve from each item's declared resolution base and are checked against the repository-root
  bound for documents and meta specs or the skill-root bound for skills and resources
- [ ] A refused read of any governed Markdown item is represented in the engine as `SkippedSubject(REFUSED_PATH)`,
  and the CLI emits an `LC002` diagnostic for every refused item read
- [ ] An unchecked symlink under `docs/` appears in coverage rather than as a diagnostic or a separate engine
  condition until corpus-directory symlinks are followed
- [ ] With no repository `skills` meta spec, the unified pipeline preserves existing diagnostics, notes, ordering,
  exit codes and `inspect` shapes, except for the link-bound diagnostics and unchecked-symlink coverage specified
  above

## References

- [prd-020](prd-020-skills-corpus.md) - Source: The skills corpus requirements (`FR-001` through `FR-007`, `FR-009`
  through `FR-011`, `FR-013`, `FR-014`, `FR-018`, `NFR-001`) that unified governed-item handling serves
- [adr-003](adr-003-project-model.md) - Supersedes in part: Origin-specific reference representation;
  declared scope and identity-versus-location separation remain in force
- [adr-010](adr-010-diagnostics.md) - Related: One diagnostic condition for link-bound escapes
- [adr-011](adr-011-rules-engine.md) - Supersedes in part: Per-kind content references, decode witnesses and
  runner loops; lazy queries and levels after detection remain in force
- [adr-015](adr-015-database.md) - Supersedes in part: Per-kind decode, analysis and link-target query
  families and document-only failed-layer skipping; revision immutability, eager model loading and value load failures
  remain in force
- [adr-016](adr-016-specifications.md) - Related: Model-computed governance and independent layer conjunction
- [adr-022](adr-022-skills-governance.md) - Related: Reserved `skills` corpus governance, built-in schema provenance
  and bounded contradiction detection
