---
name: "prd-024-shared-name-hierarchy"
description: "One name hierarchy for specs and corpus documents, so every extension knows its base chain, skills load a matched document's full chain from broadest to narrowest, and workspace inspection shows both a document's governing specs and its document base chain"
type: "prd"
status: "approved"
---

# Shared Name Hierarchy

## Problem

Lorecraft relies on two hierarchies that follow the same naming rule: in the spec directory, a namespace
spec such as `code-python-typing` specializes `code-python`, which specializes the corpus spec `code`; in each
corpus directory, a document such as `python-fn-names` specializes `python-fn`, and `spec-structure-outline`
specializes `spec-structure`, which specializes `spec`. Today the tool exposes only the governing specs of each
document. It does not expose how a corpus's specs extend one another, and it does not expose a document's own
base chain within its corpus.

Because the document hierarchy is invisible in workspace inspection and in the skills that load corpus documents, a
writer or an agent cannot see from the workspace output which broader documents an extension builds on, and an agent
loading `python-fn-names` through a discovery skill can read the narrower document alone while missing the rules its
base `python-fn` states for every function. Maintainers also need a clear, documented rule for what happens when two
layers in a chain state incompatible constraints: because every layer applies on its own by conjunction, contradictory
layers create a catch-22 in which no governed document can satisfy all layers at once.

## Goals

- Define one name-chain rule shared by specs and by documents in every corpus: a name's base is the longest
  existing name it continues with a hyphen, chains may be of any depth, and a name whose immediate prefix has no
  entry continues from the nearest existing ancestor.
- Keep a document's base chain within its corpus distinct from the specs that govern it.
- Show both hierarchies when inspecting a workspace, in both text output and machine-readable output: each spec's
  base in its corpus's spec hierarchy, each document's governing specs, and each document's base chain in
  its corpus.
- Load a matched document's full base chain, from broadest ancestor to the matched document, in the skills that load
  code rules and feature documents.
- Apply layers independently by conjunction without validating layers against each other: checks run layer by
  layer, broad to narrow, each reporting its own finding.

## Non-Goals

- **Checking spec or document layers for mutual incompatibility.** Every layer applies on its own by conjunction;
  analyzing pairs or chains of layers to prove whether any document can satisfy them together is out of scope;
  checks report each broken layer independently from broad to narrow.
- **Warning when an extension sets a higher word cap or token budget than its base.** Because every layer is checked on
  its own, the tighter limit of the base still governs; reporting redundant higher limits on the extension is not part
  of this feature.
- **Checking the prose of specs or the direction of references between extensions and bases.** The meta specs and
  the link rules own those checks; this feature neither adds nor changes them.
- **Merging layers or allowing an extension to override its base.** Conjunction is already the settled rule across
  specs, code rules and feature documents; no layer replaces or relaxes a broader one.

## User Stories

### US-1: See a document's base chain beside its governing specs (P1)

As a maintainer or agent inspecting a workspace, I want to see each document's base chain within its corpus separately
from the specs that govern it, so that I can tell which broader documents it specializes without confusing them
with its governing specs.

**Independent test:** Inspect a workspace whose corpus has `code` and `code-python` specs and the documents
`python-fn` and `python-fn-names`, with no `python` document.

```gherkin
Scenario: A document extends an existing base document in the same corpus
  Given a code corpus governed by code and code-python
  And the documents python-fn and python-fn-names in that corpus
  When the user inspects the workspace
  Then python-fn-names is shown governed by code and code-python, broad to narrow
  And python-fn-names is shown with the document base chain python-fn then python-fn-names
```

```gherkin
Scenario: A document has no broader base document in its corpus
  Given a code corpus holding python-fn and no python document
  When the user inspects the workspace
  Then python-fn is shown with a document base chain containing only python-fn
```

```gherkin
Scenario: Machine-readable inspection includes both chains
  Given a feat corpus holding spec, spec-structure and spec-structure-outline
  When the user inspects the workspace with machine-readable output
  Then spec-structure-outline lists its governing specs and its document base chain spec, spec-structure and spec-structure-outline under separate fields
```

### US-2: See how specs extend one another in a corpus (P1)

As a maintainer writing or reviewing specs, I want workspace inspection to show each spec's base in its
corpus's spec hierarchy, so that I can verify how namespace specs layer onto the corpus spec and onto
shorter namespace specs at any depth.

**Independent test:** Inspect a workspace whose `code` corpus has `code`, `code-python` and `code-python-typing`
specs, and another namespace spec `code-fn-names` with no `code-fn` spec.

```gherkin
Scenario: Multi-level namespace specs form a chain from the corpus spec
  Given a corpus with the specs code, code-python and code-python-typing
  When the user inspects the workspace
  Then code is shown as the root spec of the corpus
  And code-python is shown extending code
  And code-python-typing is shown extending code-python
```

```gherkin
Scenario: A namespace spec skips a missing intermediate namespace
  Given a corpus with the specs code and code-fn-names, and no code-fn spec
  When the user inspects the workspace
  Then code-fn-names is shown extending code without an error
```

### US-3: Load a document's full base chain when reading rules or features (P1)

As an agent loading code rules or feature documents for a task, I want selecting a specialized document to load its
entire base chain from broadest ancestor to the matched document, so that I never apply a specialized document while
missing the general rules or context its base states.

**Independent test:** Match `python-fn-names` in `/code-rules` and `spec-structure-outline` in `/feat-discovery`.

```gherkin
Scenario: Loading a matched code rule loads its base chain first
  Given the code rules python-fn and python-fn-names
  When an agent selects python-fn-names through the code-rules skill
  Then the skill instructs the agent to load python-fn first and python-fn-names after it
```

```gherkin
Scenario: Loading a matched feature document loads its base chain first
  Given the feature documents spec, spec-structure and spec-structure-outline
  When an agent selects spec-structure-outline through the feat-discovery skill
  Then the skill instructs the agent to load spec, then spec-structure, then spec-structure-outline
```

### US-4: Hold documents to every governing layer, even when layers contradict (P2)

As a maintainer checking a workspace, I want every governing spec layer applied independently without a separate
layer-incompatibility prover, with checks evaluating layers broad to narrow and reporting each broken layer,
so that checking stays simple and predictable.

**Independent test:** Check a workspace where a namespace spec and its base require mutually exclusive values on a
document they both govern.

```gherkin
Scenario: Contradictory governing layers are checked layer by layer
  Given a corpus spec and a namespace spec that require mutually exclusive values for the same field
  And a document governed by both specs
  When the maintainer checks the workspace
  Then each broken spec reports its own finding on the document from broad to narrow
  And no separate layer-incompatibility diagnostic is reported on the specs
```

## Requirements

- **FR-001:** THE SYSTEM SHALL determine the base of any document name within a corpus as the longest existing
  document name in that corpus that the name continues with a hyphen, counted by hyphen-delimited segments.
- **FR-002:** THE SYSTEM SHALL determine the base of any namespace spec within a corpus as the longest existing
  namespace spec in that corpus whose namespace the spec's namespace continues with a hyphen, or the corpus
  spec when no shorter matching namespace spec exists.
- **FR-003:** THE SYSTEM SHALL support spec chains and document base chains of any depth.
- **FR-004:** WHERE an intermediate hyphen-delimited prefix has no existing document in the corpus (or no existing
  namespace spec in the corpus), THE SYSTEM SHALL continue the chain from the nearest existing ancestor without
  reporting an error.
- **FR-005:** THE SYSTEM SHALL keep a document's base chain within its corpus separate from the chain of specs
  that govern the document.
- **FR-006:** THE SYSTEM SHALL govern each document by its corpus spec followed by every namespace spec in
  its corpus whose namespace equals the document's name or is a hyphen-delimited prefix of it, ordered broad to
  narrow along the corpus's spec hierarchy.
- **FR-007:** WHEN a user inspects a workspace in text or machine-readable output, THE SYSTEM SHALL show, for each
  corpus, the hierarchy of its specs and, for each document, both its governing specs and its document base
  chain from broadest to narrowest.
- **FR-008:** WHEN an agent selects a code rule through `/code-rules` or a feature document through `/feat-discovery`,
  THE SYSTEM SHALL direct the agent to load the matched document's entire base chain in its corpus, from broadest
  ancestor to the matched document.
- **FR-009:** WHEN a user checks a workspace, THE SYSTEM SHALL apply each governing spec layer independently by
  conjunction without running a compatibility check between layers.
- **FR-010:** WHEN governing layers in a chain contradict each other, THE SYSTEM SHALL check them layer by layer from
  broad to narrow, reporting each broken layer independently.
- **NFR-001:** THE SYSTEM SHALL derive spec chains, document base chains and document governance from declared
  names and directory listings alone, without reading document contents.
- **NFR-002:** THE SYSTEM SHALL produce deterministic inspection ordering for spec chains and document base chains
  for any given workspace state.

## Edge Cases

- **A document's immediate prefix has no file, such as `python-fn-names` when `python-fn` exists and `python` does
  not.** Its base is `python-fn`, its base chain is `python-fn` followed by `python-fn-names`, and no error is
  reported (FR-001, FR-004).
- **A namespace spec's immediate prefix has no spec, such as `code-python-typing` when `code` exists and
  `code-python` does not.** Its base in the spec hierarchy is `code`, and it still governs `python-typing` and
  `python-typing-*` documents after `code` (FR-002, FR-004, FR-006).
- **A document's name starts with a word that is a prefix of another word rather than a hyphen-delimited segment, such
  as `pythonic` beside `python` or `client` beside `cli`.** Neither extends the shorter name and neither is governed
  by its namespace spec, because matching counts whole hyphen-delimited segments (FR-001, FR-006).
- **A namespace spec matches no document in its corpus.** It still participates in the corpus's spec
  hierarchy and appears in workspace inspection with its base (FR-002, FR-007).
- **Two governing layers contradict each other.** When no document is governed by both, `lorecraft check` reports no
  finding; when a document is governed by both, `lorecraft check` checks layer by layer, broad to narrow, reporting each
  layer's finding independently (FR-009, FR-010).

## Key Entities

- **Base:** The nearest existing broader entry in the same hierarchy that an extension continues: for a document, the
  longest existing document name in the same corpus that is a hyphen-delimited prefix of its name; for a namespace
  spec, the longest existing namespace spec in the same corpus whose namespace is a hyphen-delimited prefix
  of its namespace, or the corpus spec when none exists.
- **Extension:** A spec or document whose name continues a shorter name with a hyphen and adds to or narrows what
  its base states.
- **Base chain:** The ordered sequence of existing entries in a hierarchy from the broadest ancestor down to a given
  entry itself.
- **Governing specs:** The corpus spec and the matching namespace specs of a document's corpus, ordered
  broad to narrow, each applied on its own to the document.

## Success Criteria

- **SC-001:** For every corpus and document in this repository, `lorecraft inspect` reports both the governing
  specs and the document base chain in text and machine-readable output, and every reported chain matches the
  longest-existing-hyphen-prefix rule.
- **SC-002:** `/code-rules` and `/feat-discovery` instruct agents to load the full base chain of any matched document,
  broadest first.
- **SC-003:** The documentation states the shared name-chain rule once for both hierarchies.
- **SC-004:** `lorecraft check` passes on this repository with zero errors and zero warnings.

## Assumptions

- Every corpus is flat: documents sit directly inside their corpus directory, and specs sit directly inside the
  spec directory.
- Specs and corpus documents layer onto their bases by conjunction.

## References

- [prd-008-structured-checks](prd-008-structured-checks.md) - Related: The structured checks that judge specs and documents layer by layer
