---
name: "adr-021-dependency-wrappers"
description: "Parser- and validator-style engines are contained behind Lorecraft-owned wrapper layers with stable, checked boundaries. Load when adding or changing a parser, validator, or dependency whose types or behaviour could spread through Lorecraft"
type: "adr"
status: "accepted"
---

# Keep Large Dependencies Behind Owned Wrappers

## Context

Some dependencies bring more than a callable API. Parsers and validators expose their own types, exceptions, error trees, messages, defaults, and interpretation of a format. If callers use those details directly, an upgrade or a change in those assumptions reaches every caller. The library's choices then become Lorecraft's architecture by accident, and callers can disagree about how its results should be interpreted.

For this decision, a large dependency is a parser- or validator-style engine whose types or behaviour would otherwise spread across Lorecraft, or whose rules need an adapter to produce Lorecraft's values. Examples are ruamel.yaml, jsonschema, and wenmode. Base dependencies such as pydantic, which `lorecraft.core` builds Lorecraft's own values on, are outside this wrapper rule. They are foundations for Lorecraft's types, rather than engines that parse or validate external formats at a seam.

## Decision

1. **Give each large engine its own Lorecraft wrapper as an independent sibling layer.** The `layers` contract places `yaml`, `jsonschema`, and `markdown` together in one layer (for example, `"yaml | jsonschema | markdown"`) above `core`. Import-linter treats members of that layer as peers and forbids imports between them. A wrapper may import `lorecraft.core` and the engine it wraps, but not another Lorecraft layer. This makes the wrappers available to layers above them without allowing one wrapper to depend on another.

2. **Keep each engine inside its wrapper.** For each wrapped engine, a `forbidden` contract names `lorecraft` as its source and the engine's import package as forbidden. A single ignore permits the wrapper's import, such as `lorecraft.yaml.** -> ruamel`. Where one engine has multiple import packages, each package gets the same whole-package contract pattern: JSON Schema validation's boundary includes both `jsonschema` and `referencing`. These contracts cover the whole Lorecraft package rather than an enumerated set of current callers, so a new module cannot import an engine unnoticed.

3. **Protect dependency-specific grammar modules with a `protected` contract.** For each private grammar module, the contract names that module as protected and allows its wrapper package as importer. For the YAML grammar, the shape is:

   ```toml
   [[tool.importlinter.contracts]]
   name = "The YAML grammar is read inside its package"
   type = "protected"
   protected_modules = ["lorecraft.yaml.basic_yaml"]
   allowed_importers = ["lorecraft.yaml"]
   ```

   Leave `as_packages` at its default `true`, so the wrapper and its descendants may import the grammar, while direct imports from elsewhere, including `lorecraft/__init__.py`, fail the contract. Callers may still reach the grammar indirectly through the public wrapper API. Do not use an overlapping whole-package `forbidden` contract or a wildcard source with an ignore for this boundary: neither protects the root-package importer correctly. The contract configuration itself is changed with the corresponding wrapper work; this ADR states the required shape.

4. **Return values owned by Lorecraft.** Values crossing the wrapper boundary are immutable, frozen values declared by Lorecraft. Failures cross as structured facts or typed errors with the information callers need; they do not cross as engine exceptions, error objects, or messages that callers must parse. An engine's message may be retained as opaque text only when the wrapper owns that field and callers treat it as opaque.

5. **Keep engine assumptions at the boundary.** Format dialects, accepted syntax, normalization, validator selection, ordering, defaults, and other engine-specific behaviour are decided in the wrapper. Each assumption is documented in that wrapper's `module-*` code spec and pinned by tests owned by the wrapper. Callers consume the wrapper's contract and do not repeat the engine's interpretation.

6. **Check the wrapper as a module, not just as an import filter.** Each wrapper has a `docs/code/module-lorecraft-<name>.md` code spec with a verifiable checklist. The import-linter contracts prove the import boundary; the checklist and wrapper tests prove the value, error, and behaviour boundary. An accepted ADR does not replace either check.

7. **Apply the rule to three engine seams.** The intended package boundaries are `lorecraft.yaml` for YAML parsing with ruamel.yaml, `lorecraft.jsonschema` for JSON Schema validation with jsonschema and referencing, and `lorecraft.markdown` for Markdown parsing with wenmode.

8. **Keep ADR-017 as the YAML parser choice.** [adr-017](adr-017-yaml-parser.md) chooses ruamel.yaml's event API and states its YAML-specific guarantees. This record adds the cross-engine wrapper boundary; it does not replace or supersede ADR-017.

## Consequences

- An engine upgrade should normally change one wrapper and the tests that pin its assumptions. Callers continue to depend on Lorecraft values and structured results.
- Each wrapper costs a peer layer, whole-package forbidden-import contracts for its engine, a protected contract for any private grammar module, a module code spec, and tests for the behaviour callers rely on. Those artefacts make the boundary visible and reviewable.
- The sibling `layers` contract proves that wrappers cannot import one another. Whole-package `forbidden` contracts contain external engines; a `protected` contract limits direct imports of an internal grammar module to its wrapper and descendants, including when a caller is in the root package. A module checklist and tests remain necessary because import contracts cannot prove what values or semantics cross an API.
- Base dependencies such as pydantic remain available to the Lorecraft layers that build and declare Lorecraft-owned values. They are not subject to the wrapper-layer rule.
- This record governs boundaries only. It does not choose a parser, validator, Markdown dialect, or user-visible interpretation; those decisions belong in the relevant wrapper and its architecture or code documents.

## Checklist

- [ ] Parser- and validator-style engines whose types or behaviour could spread have Lorecraft-owned wrappers as sibling members of one `layers` entry above `core`.
- [ ] Import-linter's sibling-layer rule prevents a wrapper from importing another wrapper.
- [ ] For each engine package, a `forbidden` contract names `lorecraft` as its source and permits the engine only through one ignore for its wrapper.
- [ ] Each private grammar module has a `protected` contract with that module in `protected_modules` and its wrapper package in `allowed_importers`; `as_packages` stays at its default `true`.
- [ ] The protected contract permits imports from the wrapper and its descendants, rejects direct imports from other packages including the root package, and leaves indirect access through the public wrapper available.
- [ ] Whole-package `forbidden` contracts contain external engines; the protected contract, not a `forbidden` contract, enforces the private grammar boundary.
- [ ] Values and errors crossing a wrapper boundary are Lorecraft-owned immutable values or structured facts; callers do not inspect engine types, exceptions, error trees, or messages.
- [ ] Engine-specific assumptions are stated in the wrapper's `module-*` code spec and pinned by tests owned by the wrapper.
- [ ] Each wrapper has a module code spec whose checklist makes its boundary verifiable.
- [ ] The wrapper boundaries are `lorecraft.yaml` for YAML parsing with ruamel.yaml, `lorecraft.jsonschema` for JSON Schema validation with jsonschema and referencing, and `lorecraft.markdown` for Markdown parsing with wenmode.
- [ ] The YAML parser choice remains the one in ADR-017.
- [ ] Base dependencies such as pydantic, which `lorecraft.core` builds Lorecraft's own values on, remain outside this wrapper rule.

## References

- [adr-001-snapshot-model](adr-001-snapshot-model.md) - Foundation: Package roles define which layer owns an operation
- [adr-017-yaml-parser](adr-017-yaml-parser.md) - Related: The parser choice and YAML-specific guarantees for `lorecraft.yaml`
- [module-lorecraft-yaml](../code/module-lorecraft-yaml.md) - Example: The YAML wrapper's responsibility and checkable boundary
