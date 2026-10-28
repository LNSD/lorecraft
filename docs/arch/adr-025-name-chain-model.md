---
name: "adr-025-name-chain-model"
description: "Model the spec hierarchy and the document hierarchy of each corpus with one name-chain derivation in the project model, derive governance and document base chains from it, expose both in lorecraft inspect, and let checks evaluate layers broad-to-narrow without cross-layer validation. Load when changing how lorecraft.project derives spec chains, document base chains or governance, or how lorecraft inspect renders them"
type: "adr"
status: "accepted"
---

# One Name-Chain Model for Specs and Documents

## Context

[prd-024](prd-024-shared-name-hierarchy.md) requires one shared name-chain rule across specs and corpus documents
(`FR-001` through `FR-006`), requires `lorecraft inspect` to expose both the spec hierarchy of each corpus and the
document base chain of each document alongside its governing specs (`FR-007`), requires `/code-rules` and
`/feat-discovery` to load a matched document's full base chain (`FR-008`), and requires independent layer checking broad to narrow without cross-layer validation (`FR-009`, `FR-010`).

Today [adr-016](adr-016-specifications.md) and [adr-013](adr-013-namespace-extension.md) state that both hierarchies
layer by conjunction and that a document's base chain is distinct from its governing specs, but `lorecraft.project`
models only the flat list of matching namespace specs (`NamespaceSpec.is_governing` and `namespace_order_key` in
`lorecraft.project.workspace`). The model already holds the single-step base of each hierarchy:
`Corpus.document_base(filename)` returns the `DocumentRef` a document extends, and
`WorkspaceModel.find_specification_base(ref)` returns the `SpecRef` of the spec a spec
extends; both resolve the narrowest existing ancestor through `find_narrowest_ancestor`. Neither the full chains, nor
the reverse direction, nor `lorecraft inspect` output of either chain exists.

## Decision

### One Name-Chain Derivation Over Aspect Names

`lorecraft.project` defines one pure name-chain derivation over any finite set of validated hyphen-delimited aspect
names (`AspectNamespace` for namespace specs, `AspectFilename` for corpus documents) (`FR-001` through `FR-004`,
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

### Two Hierarchies per Corpus, and Governance Over the Spec Hierarchy

Each `Corpus` in `WorkspaceModel` applies the shared name-chain derivation twice—once to its specs and once to its
documents—using only declared spec names and listed corpus filenames (`FR-001` through `FR-006`, `NFR-001`):

1. **The spec hierarchy (`FR-002`, `FR-003`, `FR-004`):** the name-chain derivation runs over the corpus's spec
   names. `WorkspaceModel` exposes it, because the spec set is read from the workspace rather than from one `Corpus`:
   `specification_base(name)`, `specification_base_chain(ref)` and `specification_extensions(ref)`.
   - `CorpusSpec` is the root of the corpus's spec hierarchy: its base is `None`, its chain is `(corpus_spec,)`,
     and its direct extensions are the `NamespaceSpec` entries whose namespace has no proper ancestor in `namespaces`.
   - For each `NamespaceSpec`, its base (`Spec`) is the `NamespaceSpec` at its resolved base namespace when one exists
     in `namespaces`, or `corpus_spec` otherwise; its chain (`tuple[Spec, ...]`) is `corpus_spec` followed by the
     `NamespaceSpec` entries along its namespace chain; and its direct extensions (`tuple[NamespaceSpec, ...]`) are the
     `NamespaceSpec` entries whose resolved base namespace is its namespace.
2. **The document hierarchy (`FR-001`, `FR-003`, `FR-004`):** `Corpus` runs the same name-chain derivation over
   `filenames` (`frozenset[AspectFilename]`). For any document in the corpus, `Corpus` exposes:
   - `document_base(filename) -> DocumentRef | None`: the `DocumentRef` in the same corpus at the resolved base
     `AspectFilename`, or `None` when the document has no shorter hyphen-prefix ancestor in the corpus.
   - `document_base_chain(filename) -> tuple[DocumentRef, ...]`: the document's existing ancestors in the corpus,
     broadest first; the document itself is not included.
   - `document_extensions(filename) -> tuple[DocumentRef, ...]`: the documents in the corpus whose `document_base` is
     this document, in the derivation's deterministic order.
3. **Governance derived from the spec hierarchy (`FR-005`, `FR-006`):** `Corpus.governance(filename)` selects
   `corpus_spec` followed by every `NamespaceSpec` in the corpus's spec hierarchy whose namespace equals
   `filename` or is a hyphen-delimited prefix of `filename`, in the hierarchy's broad-to-narrow order. A document's
   `Governance` and its `document_base_chain` remain separate queries on `Corpus` and `WorkspaceModel`: neither is derived
   from the other (`FR-005`).

```python
@dataclass(frozen=True, slots=True)
class Corpus:
    corpus_spec: CorpusSpec
    namespaces: FrozenMapping[AspectNamespace, CorpusNamespace]
    filenames: frozenset[AspectFilename]

    def document_base(self, filename: AspectFilename) -> DocumentRef | None: ...
    def document_base_chain(self, filename: AspectFilename) -> tuple[DocumentRef, ...]: ...
    def document_extensions(self, filename: AspectFilename) -> tuple[DocumentRef, ...]: ...
    def governance(self, filename: AspectFilename) -> Governance: ...


class WorkspaceModel:
    def specification_base(self, name: SpecName) -> SpecName | None: ...
    def specification_base_chain(self, ref: SpecRef) -> tuple[SpecRef, ...]: ...
    def specification_extensions(self, ref: SpecRef) -> tuple[SpecRef, ...]: ...
```

Both hierarchies run through one name-chain helper, `find_base_chain`, and stay separate queries; that separation is
the decision. Because both are built from declared spec names and listed filenames alone, editing a document's text
never invalidates `WorkspaceModel`, `Governance`, or a base chain
([adr-003](adr-003-project-model.md), [adr-015](adr-015-database.md), `NFR-001`).

### Rendering Both Hierarchies in Workspace Inspection

`lorecraft.cli.workspace_tree` renders the spec hierarchy and each document's base chain directly from the values
`Corpus` and `WorkspaceModel` expose, without computing prefix relationships in `lorecraft.cli` (`FR-007`, `NFR-002`):

1. **Text output (`render_text`):**
   - Under `specs (N)`, each spec line names its base after its files: `<spec.name>: <files> [base: <base.name>]`,
     or `[base: none]` for the corpus spec (for example,
     `code-python-typing: code-python-typing.md, code-python-typing.spec.json [base: code-python]`).
   - Under `documents (N)`, each document line shows its governing specs and its base chain under separate labels,
     the chain broadest first and ending with the document itself:
     `<filename.md> [governed_by: <governing specs>] [base_chain: <root>, ..., <filename>]`.
2. **JSON output (`render_json`, `--format json`):**
   - Each spec object carries `base: str | None`, the base spec's name, `null` for the corpus spec.
   - Each document object carries `base_chain: list[str]` beside `governed_by`: the root-relative paths of the
     document's base chain followed by the document itself, broadest first (a one-element list when the document
     extends no other document in its corpus).

### Base-First Chain Loading in Discovery Skills

As [adr-013](adr-013-namespace-extension.md) decides, `/code-rules` and `/feat-discovery` load a matched document's
full base chain in its corpus (`FR-008`). When a task or query selects `<name>.md` in `docs/code/` or `docs/feat/`, the
skill resolves every existing hyphen-prefix ancestor `<prefix>.md` in that corpus directory and reads the chain from
broadest ancestor down to `<name>.md`.

### Independent Layer Evaluation Without Cross-Layer Validation

Every governing spec layer in `Governance` applies independently by conjunction
([adr-016](adr-016-specifications.md), [adr-013](adr-013-namespace-extension.md)). Neither `load_model` nor
`lorecraft check` compares a namespace spec's frontmatter schema, outline, word caps or token budget against its
base chain for mutual compatibility (`FR-009`).

A contradiction between layers is the user's problem, and Lorecraft never validates layers against each other. Checks
run layer by layer, broad to narrow, each reporting its own finding; fixing one finding makes the other appear, which
is how the user learns of the contradiction (`FR-010`). No separate cross-layer compatibility check or catch-22
documentation is introduced.

## Consequences

- **One name-chain implementation in `lorecraft.project`.** Prefix matching and broad-to-narrow ordering live in one
  pure derivation over aspect names, shared by `Corpus`'s spec hierarchy and document hierarchy (`FR-001` through
  `FR-004`).
- **Both chains are visible in `lorecraft inspect`.** Maintainers and tools can read each namespace spec's base and
  each document's `base_chain` alongside `governed_by` in text and `--format json` (`FR-007`). This is an output
  contract addition on `inspect`; text consumers that depend on the current line format may need to adapt.
- **Discovery skills read more documents.** `/code-rules` and `/feat-discovery` load every existing base in a matched
  document's chain, which supplies the inherited rules and context at the cost of a longer read (`FR-008`).
- **No cross-layer validation in `lorecraft check`.** The checker never validates layers against each other; checks
  run layer by layer, broad to narrow, each reporting its own finding, so fixing one finding reveals the next (`FR-009`, `FR-010`).
- **What stays true:** scope and chains are derived from declared names and listings without reading document content
  ([adr-003](adr-003-project-model.md), `NFR-001`), load failures remain per-layer values in the model
  ([adr-015](adr-015-database.md)), and every governing layer applies on its own by conjunction
  ([adr-016](adr-016-specifications.md)).

## Alternatives Considered

- **Static layer-compatibility checking at load time or during `lorecraft check`.** Compare each namespace spec's
  frontmatter schema and section outline with its base chain, so a contradiction is reported on the specifications
  directly. Rejected: checks evaluate layers broad to narrow without validating layers against each other; a separate analysis
  adds unnecessary diagnostic machinery (`FR-009`, `FR-010`).
- **Two independent hierarchy derivations.** Keep a namespace-specific derivation and add a separate document-chain
  walk. This uses the fewest shared abstractions, but duplicates the prefix and ordering rules and can let inspection,
  governance and future checks disagree (`FR-001` through `FR-006`).
- **Derive a document's base chain from its governing namespace specs (or vice versa).** Rejected: a document can
  extend `python-fn.md` when no `code-python-fn` spec exists, and `code-python` governs `python-fn.md` when no
  `python.md` document exists. The two hierarchies share the name-chain rule, not their members (`FR-005`).
- **Compute document base chains inside `lorecraft.cli.workspace_tree` when rendering `inspect`.** Rejected: the CLI
  role is composition and rendering, not workspace derivation; keeping both hierarchies on `Corpus` in
  `lorecraft.project` lets `inspect`, future checks and database queries read one model.

## Checklist

Before committing code, verify:

- [ ] One pure name-chain derivation in `lorecraft.project` computes bases, chains and direct extensions for both
  spec namespaces and document filenames by longest existing hyphen-delimited prefix
- [ ] `WorkspaceModel` exposes the spec hierarchy (`specification_base`, `specification_base_chain`,
  `specification_extensions`) and `Corpus` the document hierarchy (`document_base`, `document_base_chain`,
  `document_extensions`), without reading document content
- [ ] `Corpus.governance` and `Corpus.document_base_chain` are kept separate; neither is derived from the other
- [ ] `lorecraft inspect` renders each namespace spec's base and each document's base chain in both text and
  `--format json`, reading them from `WorkspaceModel` without prefix logic in `lorecraft.cli`
- [ ] `/code-rules` and `/feat-discovery` instruct agents to load the full base chain of a matched document, broadest
  first
- [ ] Neither `load_model` nor `lorecraft check` runs a cross-layer compatibility analysis; layers are checked broad to
  narrow, each reporting its own finding

## References

- [prd-024](prd-024-shared-name-hierarchy.md) - Source: The shared name-hierarchy, inspection, skill-loading and
  layer-evaluation requirements (`FR-001` through `FR-010`, `NFR-001`, `NFR-002`)
- [adr-013](adr-013-namespace-extension.md) - Foundation: Conjunction across specs, code rules and feature
  documents, separate document base chains, and base-first loading
- [adr-016](adr-016-specifications.md) - Foundation: Specs and governance, independent layer evaluation by
  conjunction, and contradictory layers leaving governed documents unsatisfiable
- [adr-003](adr-003-project-model.md) - Foundation: Project model derived from declared layout and listings rather than
  document content
- [adr-015](adr-015-database.md) - Related: The revision database opened with `WorkspaceModel`
