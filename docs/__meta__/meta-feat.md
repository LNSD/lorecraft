---
name: "meta-feat"
description: "Responsibility of the `feat` meta specs in docs/__meta__: `feat.md` and `feat-*.md`, the specs of the feat corpus, and what belongs in a neighbouring family instead. Load when creating or editing a `feat` meta spec"
type: "meta"
scope: "global"
---

# Feat Meta Spec Family

**Applies to `feat.md` and every `feat-*.md` in `docs/__meta__/`.** It governs those meta specs and nothing else: not
the documents of `docs/feat/`, which `feat.md` and its namespaces govern. It adds no template: a meta spec of the family keeps the
[meta](meta.md) structure, and this one adds the boundary of the family.

## Responsibility

The family has one responsibility: the rules for writing the feature docs of `docs/feat/`. `feat` is the root, with the base and extension model, structure and references every feat spec shares; each `feat-<namespace>` states a group of feat specs, such as `feat-cli`.

## Belongs Here

- **It is a meta spec whose name is `feat` or continues it with a hyphen**, such as `feat` and `feat-cli`.
- **It states how the `feat` corpus is written**, not what one document of it says.
- **It stays on its layer.** The root states what holds for the whole corpus, and a namespace states only what it
  adds for its group.

## Belongs Elsewhere

| When the rule is about | It belongs in |
|---|---|
| What holds for every meta spec | [meta](meta.md) |
| A single document of `docs/feat/` | that document, not a meta spec |
| A family other than `feat` | the meta spec of that family |

## Checklist

- [ ] Every meta spec it covers is named `feat` or `feat-<namespace>`
- [ ] No rule is about one document of `docs/feat/`
- [ ] A rule that holds for every meta spec is in [meta](meta.md), not repeated here

## References

- [meta](meta.md) - Extends: Base of the meta specs that this meta spec narrows
