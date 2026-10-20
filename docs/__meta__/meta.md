---
name: "meta"
description: "Base of the meta specs in docs/__meta__: what a spec is, how its name binds it, its frontmatter and its closing references. Load when creating or editing a spec, or deciding which family a rule belongs to"
type: "meta"
scope: "global"
---

# Spec Format

**Applies to every spec in `docs/__meta__/` through the `meta-*` family.** It is the base of
`meta-arch`, `meta-code` and `meta-feat` by name, as
[README](README.md) states for every name. Its machine-checkable half is [meta.spec.json](meta.spec.json).

## 1. What a Spec Is

A **spec** states how the documents of one corpus under `docs/` are
written, so that a writer and a check read the same rules. It is not one of those documents. It binds the shape of
a corpus, and says nothing about what a document of the corpus decides, requires or describes.

A spec is a pair of files at one name in `docs/__meta__/`: the prose `<name>.md` a reader loads, and the
`<name>.spec.json` holding the rules a check can decide. [README](README.md) states how the name binds a pair to the
documents it governs, and how layers stack; this meta spec states how a spec is written.

## 2. Families

A spec belongs to the family of the corpus it governs, which its name begins with: `arch`, `code` or `feat`.
Each family has a root named for the corpus alone, `arch.md`, `code.md` and `feat.md`, and the namespace
specs of the family continue that name: `code-python`, `arch-adr`, `feat-cli`. The roots keep their names and keep
governing `docs/arch/`, `docs/code/` and `docs/feat/`.

The specs of a family are themselves documents, governed by the meta spec of their family:

| Family | Meta spec | Governs |
|---|---|---|
| `arch` | `meta-arch` | `arch.md` and `arch-*.md` |
| `code` | `meta-code` | `code.md` and `code-*.md` |
| `feat` | `meta-feat` | `feat.md` and `feat-*.md` |

**A meta spec governs specs and nothing else.** The family meta specs do not govern the documents of
`docs/arch/`, `docs/code/` or `docs/feat/`, and there is no meta spec of a single spec: `code-python` has no
`meta-code-python`.

## 3. Naming and Frontmatter

A spec is named `<corpus>.md` or `<corpus>-<namespace>.md`, and its `.spec.json` carries the same name.

| Field | Value | Notes |
|---|---|---|
| `name` | The filename minus `.md` | Equals the spec name |
| `description` | One sentence | What it governs, then when to load it |
| `type` | `"meta"` | Always |
| `scope` | `"global"` | Always |

Every field is required, and no other field is allowed.

## 4. Document Structure

A spec has one H1 title, first in the file, and no empty section. A namespace spec states only what it
adds to its base and links the base first under References, with the relation `Extends`. A base names none of its
extensions, in references or inline, so a root never lists the namespaces that continue it.

## 5. Template

````markdown
---
name: "{{name}}"
description: "{{What it governs, then when to load it}}"
type: "meta"
scope: "global"
---

# {{Title}}

**Applies to {{the documents it governs}}.** {{One line on its machine-checkable half.}}

## {{Section}}

{{The rules, stated once.}}

## References

- [{{base}}]({{base}}.md) - Extends: {{What it adds to}}
````

## 6. Checklist

- [ ] The pair `<name>.md` and `<name>.spec.json` share one name, and `name` matches it
- [ ] `type` is `"meta"` and `scope` is `"global"`
- [ ] The file governs either specs, as a meta spec, or the documents of its corpus, never both
- [ ] A namespace spec states only what it adds, and links its base under References
- [ ] The prose and the JSON state the same rules, changed in one commit
- [ ] No base names one of its extensions

## References

- [README](README.md) - Related: How a spec name binds the documents it governs
