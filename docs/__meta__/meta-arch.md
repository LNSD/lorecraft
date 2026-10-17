---
name: "meta-arch"
description: "Responsibility of the `arch` meta specs in docs/__meta__: `arch.md` and `arch-*.md`, the specs of the arch corpus, and what belongs in a neighbouring family instead. Load when creating or editing a `arch` meta spec"
type: "meta"
scope: "global"
---

# Arch Meta Spec Family

**Applies to `arch.md` and every `arch-*.md` in `docs/__meta__/`.** It governs those meta specs and nothing else: not
the documents of `docs/arch/`, which `arch.md` and its namespaces govern. It adds no template: a meta spec of the family keeps the
[meta](meta.md) structure, and this one adds the boundary of the family.

## Responsibility

The family has one responsibility: the rules for writing the architecture documents of `docs/arch/`. `arch` is the root, with the document numbering, frontmatter and closing references every kind shares; each `arch-<kind>` namespace states one kind of document.

## Belongs Here

- **It is a meta spec whose name is `arch` or continues it with a hyphen**, such as `arch` and `arch-adr`.
- **It states how the `arch` corpus is written**, not what one document of it says.
- **It stays on its layer.** The root states what holds for the whole corpus, and a namespace states only what it
  adds for its group.

## Belongs Elsewhere

| When the rule is about | It belongs in |
|---|---|
| What holds for every meta spec | [meta](meta.md) |
| A single document of `docs/arch/` | that document, not a meta spec |
| A family other than `arch` | the meta spec of that family |

## Checklist

- [ ] Every meta spec it covers is named `arch` or `arch-<namespace>`
- [ ] No rule is about one document of `docs/arch/`
- [ ] A rule that holds for every meta spec is in [meta](meta.md), not repeated here

## References

- [meta](meta.md) - Extends: Base of the meta specs that this meta spec narrows
