---
name: "meta-code"
description: "Responsibility of the `code` meta specs in docs/__meta__: `code.md` and `code-*.md`, the specs of the code corpus, and what belongs in a neighbouring family instead. Load when creating or editing a `code` meta spec"
type: "meta"
scope: "global"
---

# Code Meta Spec Family

**Applies to `code.md` and every `code-*.md` in `docs/__meta__/`.** It governs those meta specs and nothing else: not
the documents of `docs/code/`, which `code.md` and its namespaces govern. It adds no template: a meta spec of the family keeps the
[meta](meta.md) structure, and this one adds the boundary of the family.

## Responsibility

The family has one responsibility: the rules for writing the code specs of `docs/code/`. `code` is the root, with the principles, naming and structure every code spec shares; each `code-<namespace>` states a group of code specs, such as `code-python` and `code-module`.

## Belongs Here

- **It is a meta spec whose name is `code` or continues it with a hyphen**, such as `code` and `code-python`.
- **It states how the `code` corpus is written**, not what one document of it says.
- **It stays on its layer.** The root states what holds for the whole corpus, and a namespace states only what it
  adds for its group.

## Belongs Elsewhere

| When the rule is about | It belongs in |
|---|---|
| What holds for every meta spec | [meta](meta.md) |
| A single document of `docs/code/` | that document, not a meta spec |
| A family other than `code` | the meta spec of that family |

## Checklist

- [ ] Every meta spec it covers is named `code` or `code-<namespace>`
- [ ] No rule is about one document of `docs/code/`
- [ ] A rule that holds for every meta spec is in [meta](meta.md), not repeated here

## References

- [meta](meta.md) - Extends: Base of the meta specs that this meta spec narrows
