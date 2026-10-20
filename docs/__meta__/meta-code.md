---
name: "meta-code"
description: "Responsibility of the `code` specs in docs/__meta__: `code.md` and `code-*.md`, the specs of the code corpus, and what belongs in a neighbouring family instead. Load when creating or editing a `code` spec"
type: "meta"
scope: "global"
---

# Code Spec Family

**Applies to `code.md` and every `code-*.md` in `docs/__meta__/`.** It governs those specs and nothing else: not
the documents of `docs/code/`, which `code.md` and its namespaces govern. It adds no template: a spec of the family keeps the
[meta](meta.md) structure, and this one adds the boundary of the family.

## Responsibility

The family has one responsibility: the rules for writing the code rules of `docs/code/`. `code` is the root, with the principles, naming and structure every code rule shares; each `code-<namespace>` states a group of code rules, such as `code-python` and `code-module`.

## Belongs Here

- **It is a spec whose name is `code` or continues it with a hyphen**, such as `code` and `code-python`.
- **It states how the `code` corpus is written**, not what one document of it says.
- **It stays on its layer.** The root states what holds for the whole corpus, and a namespace states only what it
  adds for its group.

## Belongs Elsewhere

| When the rule is about | It belongs in |
|---|---|
| What holds for every spec | [meta](meta.md) |
| A single document of `docs/code/` | that document, not a spec |
| A family other than `code` | the spec of that family |

## Checklist

- [ ] Every spec it covers is named `code` or `code-<namespace>`
- [ ] No rule is about one document of `docs/code/`
- [ ] A rule that holds for every spec is in [meta](meta.md), not repeated here

## References

- [meta](meta.md) - Extends: Base of the meta specs that this meta spec narrows
