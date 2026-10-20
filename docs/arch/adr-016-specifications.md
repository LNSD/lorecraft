---
name: "adr-016-specifications"
description: "How specs govern documents: a spec is configuration the project model decodes and proves usable, or records as a failed layer, governance is computed once from a document's path, every governing spec applies on its own by conjunction, each check reads only its own keys of a structure file, and skills answer to a specification fixed in code. Load when adding a check, a spec file type or a key to a spec dialect, or deciding which specs a check applies"
type: "adr"
status: "accepted"
---

# Specs and Governance

> [!NOTE]
> Supersedes [adr-006-specifications](adr-006-specifications.md): restated unchanged except for what happens to a
> spec that cannot be loaded, which [adr-015](adr-015-database.md) records as a failed layer instead of a
> failure of the run. adr-006 binds no code.

## Context

A spec states the rules a group of documents follows. Lorecraft reads it as configuration, through the
project model, and every check applies what the model hands it.

## Decision

### A Spec Is Configuration

Each machine-checkable file of a spec is one JSON file beside its prose, of a file type its file name
pattern claims, such as the structure file that `*.spec.json` claims. It is read in a dialect
declared once, at the edge, as a strict and closed model. Decoding a file proves its rules usable, so every
decoded structure file can be applied without checking it again. The prose is written for a reader,
and no check reads it.

A spec whose structure file cannot be read, decoded or proved usable is recorded by the model as a failed
layer, and no part of it is applied: no check can say what a document breaks under rules that are themselves
broken. The failure is reported once, as an error diagnostic on the structure file, and it stops no run. A
document that a failed layer governs is skipped or judged against the layers that loaded, as the consumer reading
the model decides ([adr-015](adr-015-database.md)). The model loads every spec before any document is read.

### Governance Is Computed Once, by the Model

Which specs govern a document follows from its path alone: the corpus spec first, then every
namespace spec whose namespace matches the document's name, broad to narrow. The model computes it,
and the run hands each check the governing structure files. A check never looks a spec up.

Which documents a spec governs follows from its spec name, its filename with the file type's
pattern suffix stripped: the corpus alone, such as `code`, or the corpus and a namespace, such as `code-python`.
The name is parsed into a value of one of those two forms, and code that tells a corpus spec from a
namespace one matches on that form rather than splitting the text again.

A document that no spec governs with the keys a check reads is reported as ungoverned for that check,
which is not a failure.

### A Namespace Spec Layers onto Its Base by Conjunction

Every spec that governs a document applies on its own: the corpus spec first, then the
namespace specs from broad to narrow, by the number of hyphen-delimited tokens in their namespace
(`namespace_order_key`). The order fixes only the order of the report, never whether a document passes: a document
passes only when it passes every one. A check reports one finding for each layer the document breaks, and the
finding names that layer's file.

An extension adds or tightens and never relaxes. It may require a section its base leaves optional, narrow a field
its base declares, or set a lower cap or budget; it cannot release a document from anything its base states. No
spec is merged into another, so there is no effective spec and no aspect needs a merge rule.

A chain may be of any depth. A `code-python-fn` would make `code` < `code-python` < `code-python-fn` three layers,
each the base of the next, and `python-fn-names.md` would answer to all three.

### A Check Reads Its Own Keys

A check reads only the keys of a structure file it is about: the frontmatter schema, the outline and
its word caps, the token budget. A new rule over documents is a key in a dialect and a check that reads it, with
the dialect's declaration, its decoding and the check changed together.

Skills are governed by the Agent Skills specification, which is fixed, so it is declared once in code and never
read from a spec directory. A skill is never ungoverned.

```python
# ❌ Bad — the check finds its own spec by path: a namespace spec that narrows the corpus one
# is never applied, and a malformed file surfaces as a crash halfway through the run
@classmethod
def check(cls, subject: DocumentContext) -> tuple[Self, ...]:
    structure = json.loads(Path('docs/__meta__/code.spec.json').read_text(encoding='utf-8'))
    return cls._over_budget(subject.tokens().value, structure['tokens'])
```

```python
# ✅ Good — the model decided governance and proved every structure file usable; the check applies each
# one its context hands it on its own
@classmethod
def check(cls, subject: DocumentContext) -> tuple[Self, ...]:
    count = subject.tokens().value
    occurrences: list[Self] = []
    for structure_spec in subject.specifications().structure_specs():
        occurrences.extend(cls._over_budget(count, structure_spec.tokens))
    return tuple(occurrences)
```

## Alternatives Considered

- **Merge with override.** The specs in a chain merge into one effective spec per aspect, a
  narrower layer replacing a key its base sets, and each check runs once against the result, as ESLint, Ruff's
  `extend` and tsconfig's `extends` do. Not chosen: it buys only relaxation, which no spec in the
  repository uses, and it needs a merge rule for each aspect, which is why those tools carry exceptions such as
  tsconfig overwriting `include` and Ruff treating `select` and `ignore` apart. A finding could no longer name the
  layer that stated the rule. The validators that layer schemas, JSON Schema's `allOf` and XSD's derivation by
  restriction, use conjunction.
- **The narrowest spec governs alone.** Its base does not apply to what it governs. Not chosen: every
  extension restates what it keeps of its base, and the copies drift.

## Consequences

- A broken spec is one diagnostic on its structure file, never findings on every document it governs, and
  every document it does not govern is still checked.
- A new rule over documents changes a dialect key, its decoding and one check together; no check finds a
  spec on its own.
- A namespace spec is written against its base: it states only what it adds or tightens.
- A namespace spec that contradicts its base, for example an enum that shares no value with its base's,
  governs documents that no document can satisfy. No check names the spec as the cause: it shows only as
  findings on every document it governs, and a spec that governs no document yet hides it.

## Checklist

Before committing code, verify:

- [ ] A new spec key is declared in its dialect's model, decoded and proved usable at load, and read by a check
- [ ] A spec that cannot be read, decoded or proved usable is recorded as a failed layer, reported once as a
  diagnostic on its structure file, and never applied in part; it stops no run
- [ ] No check looks up, reads or chooses a spec; it applies the governing structure files it is handed
- [ ] A check applies each governing spec on its own, so a namespace spec never relaxes its base
- [ ] A check reports one finding for each governing spec a document breaks, naming that spec's file
- [ ] Nothing merges specs into an effective one; the order of the governing specs changes only the order of the report
- [ ] Code that tells a corpus spec from a namespace one matches on the parsed spec name's form, never on its length, an index or its text

## References

- [adr-006-specifications](adr-006-specifications.md) - Supersedes: The record this one restates
- [prd-014-resilient-model-loading](prd-014-resilient-model-loading.md) - Source: The requirements that make a
  spec that cannot be loaded a diagnostic
- [adr-015-database](adr-015-database.md) - Related: The model that records a failed layer, and the consumer that
  skips or judges partially
- [adr-001-snapshot-model](adr-001-snapshot-model.md) - Related: The model and the package roles
- [adr-003-project-model](adr-003-project-model.md) - Related: The project model that decodes specs
- [adr-010-diagnostics](adr-010-diagnostics.md) - Related: What a rule reports, and how it reaches the user
- [prd-008-structured-checks](prd-008-structured-checks.md) - Related: The requirements that assume layers apply by
  conjunction
- [adr-013-namespace-extension](adr-013-namespace-extension.md) - Related: The same conjunction for code rules and
  feat docs
- [principle-validate-at-edge](../code/principle-validate-at-edge.md) - Foundation: A dialect is decoded and proved at
  the edge
- [adr-011-rules-engine](adr-011-rules-engine.md) - Related: The runner that applies governance to each document
- [prd-020-skills-corpus](prd-020-skills-corpus.md) - Related: The skills corpus, whose namespaces layer the same
  way
- [adr-022](adr-022-skills-governance.md) - Related: Proposed replacement of fixed-only skills governance
  with a reserved corpus and bounded contradiction detection
- [adr-023](adr-023-governed-items.md) - Related: Unified governed-item reference and model-resolved governance
  descriptor
- [prd-024-shared-name-hierarchy](prd-024-shared-name-hierarchy.md) - Related: The requirements for one shared name
  hierarchy across specs and corpus documents
- [adr-025](adr-025-name-chain-model.md) - Related: The shared name-chain derivation for specs and corpus
  documents
