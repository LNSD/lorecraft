---
name: "adr-022-skills-governance"
description: "Bring skill entrypoints into reserved-corpus governance with a builtin meta-spec floor layer, independent repository layers and bounded contradiction detection. Load when implementing skills corpus loading, governance, checking or inspection"
type: "adr"
status: "proposed"
---

# Skills Corpus Governance

> [!NOTE]
> Proposed to supersede in part [adr-016](adr-016-specifications.md): its statements that skills answer only to a
> specification fixed in code and can never be ungoverned, and its absence of schema-contradiction diagnostics
> for skills. Its document governance and independent-layer model remain unchanged. adr-016 stays binding until
> this record is accepted.

## Context

[prd-020](prd-020-skills-corpus.md) requires repository rules for skill entrypoints without inventing a
second meta spec language. Today the workspace loads document corpora from meta spec names and
directories under docs/, while skill frontmatter answers to a fixed schema. Document contexts receive their
governing layers; skill contexts have no repository layers.

The existing schema declaration already generates an editor schema. The new corpus must preserve existing
findings when no repository skills meta spec exists (FR-013), expose the built-in rules as generated
documentation (FR-012), and permit an explicit opt-out (FR-009, FR-018).

Conjunction prevents a repository layer from relaxing a built-in rule. It does not identify an impossible
repository layer before skills exist. FR-008 and FR-019 require that extra diagnostic within an agreed boundary;
they do not require a general schema compatibility prover.

## Decision

### A Reserved Corpus Has Skill Entrypoints as Its Members

The project model recognises skills as a reserved corpus independently of a docs/skills/ directory (FR-001).
Its repository meta specs use the same prose and .spec.json file types as document corpora. It loads
skills meta specs before checking skill contents and retains failed layers rather than applying them in part.

The corpus obtains its members from the existing discovery of .agents/skills/ entries. A skill's listed
directory name is its aspect; governance is not derived from a resolved symlink target or from the frontmatter
name, which may itself be invalid. Existing skill identity and discovery are retained.

A skills namespace matches that aspect exactly or as a hyphen-delimited prefix. Governance is computed once
by the model and ordered broad to narrow, using the same namespace ordering as documents (FR-002 through
FR-004). Namespace layers still require the repository corpus meta spec at the skills name; they do not
become standalone corpora merely because a built-in schema exists.

Only SKILL.md receives these repository layers (FR-014). Skill resources remain outside meta-spec
governance (including repository structure files and floor schemas); resource discovery and existing link
and syntax checks remain active independently under `Always` gates. Specifying resource-specific rules or
governance models remains deferred for future exploration. The skills/ directory is not a second discovery root for the reserved corpus.

### A Built-in Layer Supplies the Default Floor

The built-in Agent Skills floor is an explicit source of governance, followed by the repository corpus layer and
matching namespace layers. It is a `BuiltinMetaSpecLayer` with `BundledOrigin` provenance, not a fabricated repository
file path, and supplies both frontmatter and structure inputs. Repository layer findings identify the repository layer;
built-in findings retain their current provenance and wording wherever FR-013 requires compatibility.

The floor schema enters as the first entry in a skill's applicable frontmatter schema tuple and is queried through
the schema registry (`query_at(schema_ref, schema_query)`). Each schema in the tuple is evaluated by one common locator, and missing-field
deduplication applies progressively across any earlier schemas in the tuple rather than through a skills-only
branch. Frontmatter rules (including directory name matching) gate uniformly on `WhenMetaSpec(FRONTMATTER)` whenever
the tuple is non-empty.

One declaration supplies the built-in field constraints, the representation exposed as the built-in schema,
and its generated documentation. No hand-maintained copy of those constraints is introduced.
Rules needing a skill's identity, such as its name matching its directory, remain rules rather than pretending
that a field schema can see a path. Builtin tool constraints (`allowed_tools_too_long` and `malformed_allowed_tools`)
are declared as part of the builtin floor under `FRONTMATTER`, preserving their warning severity and Lorecraft
recommendation attribution.

Each governing layer applies independently; there is no merged effective schema or structure specification. An absent
repository constraint leaves the built-in constraint in force. Omitting a repeated required list is therefore allowed
(FR-007, FR-020). Constraints that all layers enforce are not reinterpreted as overrides.

The structure dialect supplies frontmatter, outline, word limits and token/line budgets for skill entries (FR-005).
The structure specification dialect adds a `lines` budget beside `tokens`. The builtin Agent Skills structure file
declares a line limit of 500 lines (`too_many_lines`), counting the entire file and reporting from line 501.
Repository layers can tighten the line limit (e.g. `lines: 300`) but can never relax or waive the floor's 500-line cap.
When the builtin floor is active, skills are governed for `FRONTMATTER` and `BUDGET`. Coverage records which parts
are ungoverned, just as it does for documents.

### The Opt-out Is Global and Explicit

The root CLI option `--no-agent-skills-spec` (with `--no-builtin-skills-schema` retained as an alias) disables the entire
builtin Agent Skills floor layer and the compatibility analysis against it. The default is enabled. The setting is passed
into workspace governance for both check and inspect, so the two commands describe and enforce the same choice.

Examples:

```text
lorecraft --no-agent-skills-spec check
lorecraft --no-agent-skills-spec inspect
```

The option has no environment-variable counterpart and no repository configuration in this change.
A task recipe or CI command can persist the explicit flag.

With the option enabled, the entire builtin floor layer—its frontmatter schema, line budget, and tool constraints—is
omitted. Repository skills meta specs apply on their own (FR-009). With no repository skills specification, skills are
reported as ungoverned for `FRONTMATTER`, `STRUCTURE`, `OUTLINE`, and `BUDGET` without an error (FR-018).
The option changes meta-spec floor governance; it does not disable discovery, I/O diagnostics or unrelated link checks
such as `escaping_link`.

### Contradiction Detection Is Bounded

While the builtin Agent Skills floor is enabled, the project model examines each repository skills layer's direct
frontmatter.properties.name and frontmatter.properties.description constraints. Both fields are required
by the built-in schema, so an impossible constraint on either cannot be avoided by omitting the field.
Adding a declarative line budget does not expand contradiction detection into a general structural constraint prover:
preflight remains focused on direct required string constraints.

The compatibility check reports these cases:

- The field schema is false, forbidding the required field.
- An explicit type excludes string.
- Direct minLength and maxLength bounds intersect the built-in bounds in an empty interval.
- A direct enum or const leaves no candidate satisfying the built-in field schema and the direct type and
  length constraints above. If enum and const both occur, a candidate must satisfy both.

An omitted constraint is not a contradiction. The analysis does not infer constraints through references,
combinators, conditionals or patterns. It does not analyse optional fields, line limits, or interactions between repository
layers. Those constructs remain accepted by the common schema and structure dialects and apply when skills are validated.
Passing preflight therefore does not certify that the schemas or structure limits are jointly satisfiable.

A detected contradiction is recorded against the repository specification with the field and contradicted
built-in rule, even in a workspace with no skills (FR-008). It is an unusable layer under the existing
failed-layer model: check reports the error and fails (FR-019); inspect follows its existing behaviour for
an unusable meta spec. It is not repeated as a contradiction finding on every skill.

A consumer skips governed subjects under a failed layer according to its existing failed-layer policy.
Disabling the builtin floor removes only this compatibility analysis, not validation of the repository
meta spec's own syntax, structure dialect, and usability.

### Reserved Docs Names Are Reported and Excluded

A corpus detected under docs/ with a reserved name is recorded as a layout overlap, not loaded as an ordinary
document corpus. Its documents receive no skills rules and are not checked (FR-015, FR-016).
The overlap rule reports the directory once, at warning severity by default.

The overlap is promoted to an error, making check fail (FR-017), with a general check option
`--error <selectors>`. It reuses the existing rule code and prefix selectors and their validation, and promotes
only the matching rules that are already enabled: it never enables an ignored rule, and unrelated warnings keep
their severity. A dedicated overlap option and a global `--warnings-as-errors` switch are rejected: the first adds
a bespoke surface for one rule, the second makes every warning fatal.
The reserved name remains reserved when the builtin floor is disabled.

### Inspection Reads the Same Governance

Inspect exposes repository skills layers in broad-to-narrow order and identifies whether the builtin floor layer
is enabled (FR-011). Its text and machine-readable views derive from the same model used by check, reflecting
the active floor layer across frontmatter and budget coverage.
It does not create a second matching algorithm or require a docs/skills/ directory.

## Consequences

- Skill entrypoints gain repository frontmatter, outline, token, and line rules. The structure dialect adds
  `lines` alongside `tokens` without allowing narrower layers to erase broader constraints.
- Existing skills diagnostics and identity survive the migration. Generated schema output and builtin structure
  definitions preserve representative existing findings when no repository skills meta spec is present.
- Skills may be governed without a physical corpus directory. Code that assumes every corpus maps to a docs/
  path must distinguish the reserved corpus rather than constructing a nonexistent document path.
- Built-in origin and repository origin must both be representable in governance and inspection without
  inventing files. This adds a source distinction but preserves traceable findings.
- The bounded analysis catches common impossible required-field constraints before any skills exist.
  More involved contradictions and line-budget interactions can remain hidden until a skill exercises them; this is an explicit limit.
- The opt-out deliberately permits skills outside the built-in standard and even ungoverned skills, omitting the
  entire builtin floor layer (frontmatter schema, line budget, and tool constraints). It is visible per invocation
  rather than inherited from an environment variable.
- A docs/skills/ directory loses ordinary document-corpus semantics. Its overlap diagnostic explains why its
  documents are unchecked; making that diagnostic an error does not make those documents governed.
- Reading the floor schema through the schema registry unifies skills and document frontmatter validation into one
  ordered schema tuple, removing bespoke skill-only branches from `frontmatter_schema_problems`.
- Progressive missing-field deduplication across earlier schemas in the tuple preserves the guarantee that an
  absent field required by both floor and repository layers is reported once, without treating the floor as an
  architectural exception.
- Builtin tool constraints (`allowed_tools_too_long`, `malformed_allowed_tools`) and line limit (`too_many_lines`)
  execute as declarative meta-spec-governed rules under `WhenMetaSpec(FRONTMATTER)` and `WhenMetaSpec(BUDGET)`,
  rather than unconditional ad-hoc checks.
- Link escaping checks (`escaping_link`) remain an invariant check under `Always()`, ensuring skill resources and
  entrypoints do not escape containment regardless of meta-spec floor opt-out.

## Alternatives Considered

- **Conjunction alone.** The simplest implementation preserves the existing layer model and ensures repository
  rules cannot weaken the built-in rules. It cannot identify the faulty meta spec independently of skill
  contents, so it does not provide the agreed early contradiction diagnostic.
- **A restricted skills extension dialect.** Limiting schemas to constraints with complete compatibility checks
  gives a stronger guarantee within that subset, but creates a second dialect and reduces parity with documents.
- **Bounded analysis plus conjunction.** Chosen: keep the common language and independent validation, with a
  specific early-detection boundary rather than an implied complete proof.
- **Environment or repository opt-out configuration alongside the flag.** These persist the choice across
  commands but add hidden process state or a new configuration location and precedence rules. A CLI-only flag
  makes the choice explicit and is sufficient for this change.
- **Partial opt-out (schema only vs line limits).** Rejected: treating the Agent Skills specification floor as
  a coherent bundle ensures `--no-agent-skills-spec` provides a clean opt-out for custom skill standards.

## Checklist

- [ ] Skills governance uses the listed skill name and existing namespace matching, never the resolved target name
- [ ] Skills meta specs load without docs/skills/ and apply only to SKILL.md; skill resources remain outside meta-spec governance
- [ ] Every layer applies independently, with one declaration supplying built-in constraints and generated docs
- [ ] The builtin Agent Skills floor supplies a builtin meta-spec layer (frontmatter schema, tool constraints, and 500-line budget)
- [ ] The structure specification dialect supports `lines` budget alongside `tokens`
- [ ] A skill with no repository skills meta spec retains the existing findings under the default setting
- [ ] The opt-out `--no-agent-skills-spec` disables the entire builtin floor layer, affects check and inspect alike, and allows ungoverned skills without an error
- [ ] Compatibility analysis covers only the stated direct required-field constraints and is disabled by opt-out
- [ ] A detected contradiction names the faulty meta spec and fails check even when no skill exists
- [ ] A reserved docs corpus is excluded and reported once, warning by default and promoted to error by `--error <selectors>`
- [ ] Inspection reports the same governing layers the checker uses, with honest built-in provenance across frontmatter and budget
- [ ] The floor schema is queried via `query_at(schema_ref, schema_query)` as the first entry in the skill's applicable frontmatter schema tuple
- [ ] Missing-field deduplication operates progressively across earlier schemas in the applicable tuple

## References

- [prd-020](prd-020-skills-corpus.md) - Source: The skills corpus requirements and contradiction-detection boundary
- [adr-016](adr-016-specifications.md) - Proposed replacement in part: Fixed-only skills governance; independent
  document layers and failed-layer semantics remain in force
- [adr-023](adr-023-governed-items.md) - Related: Unified governed-item reference, model-resolved descriptor and
  hierarchical resource governance identity
- [adr-028](adr-028-schema-registry.md) - Foundation: Central schema registry, query-backed schema resolution and
  unified frontmatter schema path
