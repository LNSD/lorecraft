---
name: "adr-025-name-chain-model"
description: "Model the meta spec hierarchy and the document hierarchy of each corpus with one name-chain derivation in the project model, derive governance and document base chains from it, expose both in lorecraft inspect, and document contradictory layers as a catch-22 without a compatibility check. Load when changing how lorecraft.project derives meta spec chains, document base chains or governance, or how lorecraft inspect renders them"
type: "adr"
status: "proposed"
---

# One Name-Chain Model for Meta Specs and Documents

## Context

[prd-024](prd-024-shared-name-hierarchy.md) requires one shared name-chain rule across meta specs and corpus documents
(`FR-001` through `FR-006`), requires `lorecraft inspect` to expose both the meta spec hierarchy of each corpus and the
document base chain of each document alongside its governing meta specs (`FR-007`), requires `/code-rules` and
`/feat-discovery` to load a matched document's full base chain (`FR-008`), and requires independent layer checking
without a cross-layer compatibility prover while documenting that contradictory layers create a catch-22 (`FR-009`,
`FR-010`).

Today [adr-016](adr-016-specifications.md) and [adr-013](adr-013-namespace-extension.md) state that both hierarchies
layer by conjunction and that a document's base chain is distinct from its governing meta specs, but `lorecraft.project`
models only the flat list of matching namespace meta specs (`NamespaceSpec.is_governing` and `namespace_order_key` in
`lorecraft.project.workspace`). The model already holds the single-step base of each hierarchy:
`Corpus.document_base(filename)` returns the `DocumentRef` a document extends, and
`WorkspaceModel.find_specification_base(ref)` returns the `SpecRef` of the meta specification a meta specification
extends; both resolve the narrowest existing ancestor through `find_narrowest_ancestor`. Still unbuilt are the full
chains (`document_chain`, the meta spec chain), the reverse direction (`document_extensions`) and the
`lorecraft inspect` output, so `inspect` cannot show either chain.

## Decision

### One Name-Chain Derivation Over Aspect Names

`lorecraft.project` defines one pure name-chain derivation over any finite set of validated hyphen-delimited aspect
names (`AspectNamespace` for namespace meta specs, `AspectFilename` for corpus documents) (`FR-001` through `FR-004`,
`NFR-001`, `NFR-002`):

1. **Prefix and order:** Name `a` is a proper hyphen-delimited ancestor of name `b` when `str(b)` starts with
   `f'{a}-'`. Ancestors of one name are totally ordered from broadest to narrowest by their hyphen-delimited segment
   count (`str(name).count('-')`), so no two ancestors of the same name ever tie. Sibling names that do not extend one
   another are ordered by `(segment count, str(name))` (`NFR-002`).
2. **Base:** For any name in the set, its base is its narrowest existing proper ancestor in that set (the candidate
   with the highest segment count), or `None` when the set holds no proper ancestor of the name (`FR-001`, `FR-002`).
   When an intermediate hyphen prefix is absent from the set, the nearest existing broader prefix in the set is chosen
   directly without error (`FR-004`).
3. **Chain and direct extensions:** A name's chain is the tuple of its existing proper ancestors in the set, ordered
   broadest to narrowest, followed by the name itself (`FR-003`). Its direct extensions are the names in the set whose
   resolved base equals this name, in the derivation's deterministic order.

### Two Hierarchies per Corpus, and Governance Over the Meta Spec Hierarchy

Each `Corpus` in `WorkspaceModel` applies the shared name-chain derivation twice—once to its meta specs and once to its
documents—using only declared meta spec names and listed corpus filenames (`FR-001` through `FR-006`, `NFR-001`):

1. **The meta spec hierarchy (`FR-002`, `FR-003`, `FR-004`):** `Corpus` runs the name-chain derivation over the keys of
   `namespaces` (`frozenset[AspectNamespace]`).
   - `CorpusSpec` is the root of the corpus's meta spec hierarchy: its base is `None`, its chain is `(corpus_spec,)`,
     and its direct extensions are the `NamespaceSpec` entries whose namespace has no proper ancestor in `namespaces`.
   - For each `NamespaceSpec`, its base (`Spec`) is the `NamespaceSpec` at its resolved base namespace when one exists
     in `namespaces`, or `corpus_spec` otherwise; its chain (`tuple[Spec, ...]`) is `corpus_spec` followed by the
     `NamespaceSpec` entries along its namespace chain; and its direct extensions (`tuple[NamespaceSpec, ...]`) are the
     `NamespaceSpec` entries whose resolved base namespace is its namespace.
2. **The document hierarchy (`FR-001`, `FR-003`, `FR-004`):** `Corpus` runs the same name-chain derivation over
   `filenames` (`frozenset[AspectFilename]`). For any document in the corpus, `Corpus` exposes:
   - `document_base(filename) -> DocumentRef | None`: the `DocumentRef` in the same corpus at the resolved base
     `AspectFilename`, or `None` when the document has no shorter hyphen-prefix ancestor in the corpus.
   - `document_chain(filename) -> tuple[DocumentRef, ...]`: the document's base chain in the corpus, from the broadest
     existing ancestor `DocumentRef` down to `DocumentRef(corpus=self.name, filename=filename)` itself.
   - `document_extensions(filename) -> tuple[DocumentRef, ...]`: the documents in the corpus whose `document_base` is
     this document, in the derivation's deterministic order.
3. **Governance derived from the meta spec hierarchy (`FR-005`, `FR-006`):** `Corpus.governance(filename)` selects
   `corpus_spec` followed by every `NamespaceSpec` in the corpus's meta spec hierarchy whose namespace equals
   `filename` or is a hyphen-delimited prefix of `filename`, in the hierarchy's broad-to-narrow order. A document's
   `Governance` and its `document_chain` remain separate queries on `Corpus` and `WorkspaceModel`: neither is derived
   from the other (`FR-005`).

```python
@dataclass(frozen=True, slots=True)
class Corpus:
    corpus_spec: CorpusSpec
    namespaces: FrozenMapping[AspectNamespace, CorpusNamespace]
    filenames: frozenset[AspectFilename]

    # Meta spec base: built as WorkspaceModel.find_specification_base(ref: SpecRef) -> SpecRef | None
    def spec_chain(self, namespace: AspectNamespace) -> tuple[Spec, ...]: ...  # proposed
    def document_base(self, filename: AspectFilename) -> DocumentRef | None: ...  # built
    def document_chain(self, filename: AspectFilename) -> tuple[DocumentRef, ...]: ...
    def governance(self, filename: AspectFilename) -> Governance: ...
```

Of the sketch, only `document_base` and `WorkspaceModel.find_specification_base` exist today; `spec_chain`,
`document_chain` and `document_extensions` are proposals. The meta spec base stays on `WorkspaceModel` under its
current name, which takes a `SpecRef`, because the meta specification set is read from the workspace rather than from
one `Corpus`. Names in the sketch are illustrative; the separation of the two chains on `Corpus` over one name-chain
helper is the decision. Because `Corpus` builds both hierarchies from `namespaces` and `filenames` alone, editing a
document's text never invalidates `WorkspaceModel`, `Governance`, or `document_chain`
([adr-003](adr-003-project-model.md), [adr-015](adr-015-database.md), `NFR-001`).

### Rendering Both Hierarchies in Workspace Inspection

`lorecraft.cli.workspace_tree` renders the meta spec hierarchy and each document's base chain directly from the values
`Corpus` exposes, without computing prefix relationships in `lorecraft.cli` (`FR-007`, `NFR-002`):

1. **Text output (`render_text`):**
   - Under `specs (N)`, the corpus meta spec line remains `<corpus>: <files>`, and each namespace meta spec line names
     its base meta spec in brackets after the meta spec name: `<spec.name> [extends <base.name>]: <files>` (for
     example, `code-python [extends code]: code-python.md, code-python.spec.json` and
     `code-python-typing [extends code-python]: code-python-typing.md, code-python-typing.spec.json`).
   - Under `documents (N)`, each document line keeps its governing meta specs in brackets and, when its `document_chain`
     has more than one entry, appends its base chain of document filenames from broadest ancestor to the document
     itself, separated by ` < `: `<filename.md> [<governing specs>] (chain: <root.md> < ... < <filename.md>)`. A
     document that is the root of its own document chain prints as `<filename.md> [<governing specs>]`, unchanged.
2. **JSON output (`render_json`, `--format json`):**
   - `_SpecJson` gains `base: str | None`, holding the `stem` of the meta spec's base (`None` for the corpus meta spec,
     and the base meta spec's name for each namespace meta spec).
   - `_DocumentJson` does not yet carry a base chain; this ADR proposes adding
     `base_chain: list[str]`, holding the root-relative paths of `corpus.document_chain(filename)`
     from broadest ancestor to the document itself (a one-element list `[str(ref.path)]` when the document extends no
     other document in its corpus).

### Base-First Chain Loading in Discovery Skills

As [adr-013](adr-013-namespace-extension.md) decides, `/code-rules` and `/feat-discovery` load a matched document's
full base chain in its corpus (`FR-008`). When a task or query selects `<name>.md` in `docs/code/` or `docs/feat/`, the
skill resolves every existing hyphen-prefix ancestor `<prefix>.md` in that corpus directory and reads the chain from
broadest ancestor down to `<name>.md`.

### Independent Layer Evaluation and the Catch-22 of Contradictions

Every governing meta spec layer in `Governance` applies independently by conjunction
([adr-016](adr-016-specifications.md), [adr-013](adr-013-namespace-extension.md)). Neither `load_model` nor
`lorecraft check` compares a namespace meta spec's frontmatter schema, outline, word caps or token budget against its
base chain for mutual compatibility (`FR-009`).

When two layers in a chain state mutually exclusive requirements—such as disjoint frontmatter `enum` sets, incompatible
patterns, or section orders that cannot both hold—they create a catch-22 situation: no document governed by both layers
can satisfy every layer at once. `lorecraft check` evaluates each layer on its own and reports each broken layer's
diagnostic on the governed documents (`FR-010`). The feature documentation and meta spec documentation state this
catch-22 explicitly so authors know that layer contradictions surface as unsatisfiable governed documents rather than a
separate meta spec compatibility diagnostic.

## Consequences

- **One name-chain implementation in `lorecraft.project`.** Prefix matching and broad-to-narrow ordering live in one
  pure derivation over aspect names, shared by `Corpus`'s meta spec hierarchy and document hierarchy (`FR-001` through
  `FR-004`).
- **Both chains are visible in `lorecraft inspect`.** Maintainers and tools can read each namespace meta spec's base and
  each document's `base_chain` alongside `governed_by` in text and `--format json` (`FR-007`). This is an output
  contract addition on `inspect`; text consumers that depend on the current line format may need to adapt.
- **Discovery skills read more documents.** `/code-rules` and `/feat-discovery` load every existing base in a matched
  document's chain, which supplies the inherited rules and context at the cost of a longer read (`FR-008`).
- **No static compatibility prover in `lorecraft check`.** The checker adds no separate mechanism for deciding whether
  layers are compatible; contradictory layers remain a documented catch-22, and checks report each broken layer on
  governed documents (`FR-009`, `FR-010`).
- **What stays true:** scope and chains are derived from declared names and listings without reading document content
  ([adr-003](adr-003-project-model.md), `NFR-001`), load failures remain per-layer values in the model
  ([adr-015](adr-015-database.md)), and every governing layer applies on its own by conjunction
  ([adr-016](adr-016-specifications.md)).

## Alternatives Considered

- **Static layer-compatibility checking at load time or during `lorecraft check`.** Compare each namespace meta spec's
  frontmatter schema and section outline with its base chain, so a contradiction is reported on the specifications
  directly. Rejected: the settled behavior keeps each layer independently applicable and documents the catch-22 on
  governed documents; a separate analysis adds another diagnostic path without changing that rule (`FR-009`, `FR-010`).
- **Two independent hierarchy derivations.** Keep a namespace-specific derivation and add a separate document-chain
  walk. This uses the fewest shared abstractions, but duplicates the prefix and ordering rules and can let inspection,
  governance and future checks disagree (`FR-001` through `FR-006`).
- **Derive a document's base chain from its governing namespace meta specs (or vice versa).** Rejected: a document can
  extend `python-fn.md` when no `code-python-fn` meta spec exists, and `code-python` governs `python-fn.md` when no
  `python.md` document exists. The two hierarchies share the name-chain rule, not their members (`FR-005`).
- **Compute document base chains inside `lorecraft.cli.workspace_tree` when rendering `inspect`.** Rejected: the CLI
  role is composition and rendering, not workspace derivation; keeping both hierarchies on `Corpus` in
  `lorecraft.project` lets `inspect`, future checks and database queries read one model.

## Deferred

| Deferred | What the design keeps open |
|---|---|
| Reference-direction checks | A future rule in `lorecraft.rules` can read `Corpus.document_base` and `WorkspaceModel.find_specification_base` to verify that an extension links to its base and a base never links to its extensions |
| Governing `docs/__meta__/` prose | Validating the prose files of `docs/__meta__/` against a meta spec of their own is left to a follow-up feature |

## Checklist

Before committing code, verify:

- [ ] One pure name-chain derivation in `lorecraft.project` computes bases, chains and direct extensions for both
  meta spec namespaces and document filenames by longest existing hyphen-delimited prefix
- [ ] `Corpus` exposes both the meta spec hierarchy (`CorpusSpec` root, `NamespaceSpec` base and chain) and the
  document hierarchy (`document_base`, `document_chain`, `document_extensions`) without reading document content
- [ ] `Corpus.governance` and `Corpus.document_chain` are kept separate; neither is derived from the other
- [ ] `lorecraft inspect` renders each namespace meta spec's base and each document's base chain in both text and
  `--format json`, reading them from `WorkspaceModel` without prefix logic in `lorecraft.cli`
- [ ] `/code-rules` and `/feat-discovery` instruct agents to load the full base chain of a matched document, broadest
  first
- [ ] Neither `load_model` nor `lorecraft check` runs a cross-layer compatibility analysis, and the documentation
  states that contradictory layers create a catch-22 on governed documents

## References

- [prd-024](prd-024-shared-name-hierarchy.md) - Source: The shared name-hierarchy, inspection, skill-loading and
  catch-22 requirements (`FR-001` through `FR-010`, `NFR-001`, `NFR-002`)
- [adr-013](adr-013-namespace-extension.md) - Foundation: Conjunction across meta specs, code rules and feature
  documents, separate document base chains, and base-first loading
- [adr-016](adr-016-specifications.md) - Foundation: Meta specs and governance, independent layer evaluation by
  conjunction, and contradictory layers leaving governed documents unsatisfiable
- [adr-003](adr-003-project-model.md) - Foundation: Project model derived from declared layout and listings rather than
  document content
- [adr-015](adr-015-database.md) - Related: The revision database opened with `WorkspaceModel`
