---
name: "adr-006-specifications"
description: "How meta specs govern documents: a meta spec is configuration the project model decodes and proves usable, governance is computed once from a document's path, every governing meta spec applies on its own by conjunction, each check reads only its own keys of a structure file, and skills answer to a specification fixed in code. Load when adding a check, a meta spec file type or a key to a meta spec dialect, or deciding which meta specs a check applies"
type: "adr"
status: "accepted"
---

# Meta Specs and Governance

## Context

A meta spec states the rules a group of documents follows. Lorecraft reads it as configuration, through the
project model, and every check applies what the model hands it.

## Decision

### A Meta Spec Is Configuration

Each machine-checkable file of a meta spec is one JSON file beside its prose, of a file type its file name
pattern claims, such as the structure file that `*.structure.json` claims. It is read in a dialect
declared once, at the edge, as a strict and closed model. Decoding a file proves its rules usable, so every
decoded structure file can be applied without checking it again. The prose is written for a reader,
and no check reads it.

A meta spec that cannot be read, decoded or proved usable is a failure of the run, not a finding: no check
can say what a document breaks while the rules themselves are broken. The model loads every meta spec before
any document is read.

### Governance Is Computed Once, by the Model

Which meta specs govern a document follows from its path alone: the corpus meta spec first, then every
namespace meta spec whose namespace matches the document's name, broad to narrow. The model computes it,
and the run hands each check the governing structure files. A check never looks a meta spec up.

Which documents a meta spec governs follows from its meta spec name, its filename with the file type's
pattern suffix stripped: the corpus alone, such as `code`, or the corpus and a namespace, such as `code-python`.
The name is parsed into a value of one of those two forms, and code that tells a corpus meta spec from a
namespace one matches on that form rather than splitting the text again.

A document that no meta spec governs with the keys a check reads is reported as ungoverned for that check,
which is not a failure.

### A Namespace Meta Spec Layers onto Its Base by Conjunction

Every meta spec that governs a document applies on its own: the corpus meta spec first, then the
namespace meta specs from broad to narrow, by the number of hyphen-delimited tokens in their namespace
(`namespace_order_key`). The order fixes only the order of the report, never whether a document passes: a document
passes only when it passes every one. A check reports one finding for each layer the document breaks, and the
finding names that layer's file.

An extension adds or tightens and never relaxes. It may require a section its base leaves optional, narrow a field
its base declares, or set a lower cap or budget; it cannot release a document from anything its base states. No
meta spec is merged into another, so there is no effective meta spec and no aspect needs a merge rule.

A chain may be of any depth. A `code-python-fn` would make `code` < `code-python` < `code-python-fn` three layers,
each the base of the next, and `python-fn-names.md` would answer to all three.

### A Check Reads Its Own Keys

A check reads only the keys of a structure file it is about: the frontmatter schema, the outline and
its word caps, the token budget. A new rule over documents is a key in a dialect and a check that reads it, with
the dialect's declaration, its decoding and the check changed together.

Skills are governed by the Agent Skills specification, which is fixed, so it is declared once in code and never
read from a meta spec directory. A skill is never ungoverned.

```python
# ❌ Bad — the check finds its own meta spec by path: a namespace meta spec that narrows the corpus one
# is never applied, and a malformed file surfaces as a crash halfway through the run
@classmethod
def check(cls, subject: DocumentContext) -> tuple[Self, ...]:
    structure = json.loads(Path('docs/__meta__/code.structure.json').read_text(encoding='utf-8'))
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

- **Merge with override.** The meta specs in a chain merge into one effective meta spec per aspect, a
  narrower layer replacing a key its base sets, and each check runs once against the result, as ESLint, Ruff's
  `extend` and tsconfig's `extends` do. Not chosen: it buys only relaxation, which no meta spec in the
  repository uses, and it needs a merge rule for each aspect, which is why those tools carry exceptions such as
  tsconfig overwriting `include` and Ruff treating `select` and `ignore` apart. A finding could no longer name the
  layer that stated the rule. The validators that layer schemas, JSON Schema's `allOf` and XSD's derivation by
  restriction, use conjunction.
- **The narrowest meta spec governs alone.** Its base does not apply to what it governs. Not chosen: every
  extension restates what it keeps of its base, and the copies drift.

## Consequences

- A broken meta spec stops the run before any document is read, instead of surfacing as findings.
- A new rule over documents changes a dialect key, its decoding and one check together; no check finds a
  meta spec on its own.
- A namespace meta spec is written against its base: it states only what it adds or tightens.
- A namespace meta spec that contradicts its base, for example an enum that shares no value with its base's,
  governs documents that no document can satisfy. No check names the meta spec as the cause: it shows only as
  findings on every document it governs, and a meta spec that governs no document yet hides it.

## Checklist

Before committing code, verify:

- [ ] A new meta spec key is declared in its dialect's model, decoded and proved usable at load, and read by a check
- [ ] A meta spec that cannot be decoded or is unusable stops the run; it is never reported as a finding
- [ ] No check looks up, reads or chooses a meta spec; it applies the governing structure files it is handed
- [ ] A check applies each governing meta spec on its own, so a namespace meta spec never relaxes its base
- [ ] A check reports one finding for each governing meta spec a document breaks, naming that meta spec's file
- [ ] Nothing merges meta specs into an effective one; the order of the governing meta specs changes only the order of the report
- [ ] Code that tells a corpus meta spec from a namespace one matches on the parsed meta spec name's form, never on its length, an index or its text

## References

- [#208](https://github.com/LNSD/lorecraft/issues/208) - Source: Whether a namespace extension layers onto its base or
  overrides it
- [adr-001-snapshot-model](adr-001-snapshot-model.md) - Related: The model and the package roles
- [adr-003-project-model](adr-003-project-model.md) - Related: The project model that decodes meta specs
- [adr-010-diagnostics](adr-010-diagnostics.md) - Related: What a rule reports, and how it reaches the user
- [prd-008-structured-checks](prd-008-structured-checks.md) - Related: The requirements that assume layers apply by
  conjunction
- [adr-013-namespace-extension](adr-013-namespace-extension.md) - Related: The same conjunction for code specs and
  feat specs
- [principle-validate-at-edge](../code/principle-validate-at-edge.md) - Foundation: A dialect is decoded and proved at
  the edge
