---
name: "arch-specifications"
description: "How specifications govern documents: a specification is configuration the project model decodes and proves usable, governance is computed once from a document's path, each check reads only its own aspect's keys, and skills answer to a specification fixed in code. Load when adding a check, an aspect or a key to a specification dialect, or deciding which specifications a check applies"
type: "arch"
scope: "global"
---

# Specifications and Governance

A specification states the rules a group of documents follows. Lorecraft reads it as configuration, through the
project model, and every check applies what the model hands it.

## A Specification Is Configuration

Each machine-checkable aspect of a specification is one JSON file beside its prose, read in a dialect declared
once, at the edge, as a strict and closed model. Decoding a file proves its rules usable, so every decoded aspect
can be applied without checking it again. The prose is written for a reader, and no check reads it.

A specification that cannot be read, decoded or proved usable is a failure of the run, not a finding: no check
can say what a document breaks while the rules themselves are broken. The model loads every specification before
any document is read.

## Governance Is Computed Once, by the Model

Which specifications govern a document follows from its path alone: the corpus specification first, then every
namespace specification whose namespace matches the document's name, broad to narrow. The model computes it,
and the run hands each check the governing aspects. A check never looks a specification up.

Each governing specification is applied on its own. A namespace specification adds to its corpus one and
cannot relax it, so a document must pass every one. A document that no specification governs for an aspect is
reported as ungoverned for that aspect, which is not a failure.

## A Check Reads Its Own Keys

A check reads only the keys of an aspect it is about: the frontmatter schema, the outline and its word caps, the
token budget. A new rule over documents is a key in a dialect and a check that reads it, with the dialect's
declaration, its decoding and the check changed together.

Skills are governed by the Agent Skills specification, which is fixed, so it is declared once in code and never
read from a specification directory. A skill is never ungoverned.

```python
# ❌ Bad — the check finds its own specification by path: a namespace specification that narrows the corpus one
# is never applied, and a malformed file surfaces as a crash halfway through the run
def validate_budget(doc: DocRef, count: int) -> tuple[Violation, ...]:
    rules = json.loads(Path(f'docs/__meta__/{doc.corpus}.structure.json').read_text(encoding='utf-8'))
    return _over_budget(count, rules['tokens'])
```

```python
# ✅ Good — the model decided governance and proved every aspect usable; the check applies each one on its own
def validate_budget(aspects: tuple[BudgetRules, ...], *, count: int) -> tuple[Violation, ...]:
    return tuple(v for aspect in aspects for v in _over_budget(count, aspect.tokens))
```

## Checklist

Before committing code, verify:

- [ ] A new specification key is declared in its dialect's model, decoded and proved usable at load, and read by a check
- [ ] A specification that cannot be decoded or is unusable stops the run; it is never reported as a finding
- [ ] No check looks up, reads or chooses a specification; it applies the governing aspects it is handed
- [ ] A check applies each governing specification on its own, so a namespace specification never relaxes its corpus one

## References

- [arch-snapshot-model](arch-snapshot-model.md) - Related: The model and the package roles
- [arch-project-model](arch-project-model.md) - Related: The project model that decodes specifications
- [arch-findings](arch-findings.md) - Related: What a check reports, and how
- [principle-validate-at-edge](principle-validate-at-edge.md) - Foundation: A dialect is decoded and proved at
  the edge
