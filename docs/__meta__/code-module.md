---
name: "code-module"
description: "Structure template for `docs/code/module-*.md` rule documents, one per package, each stating the package's single responsibility, its role, what belongs in it and what does not, and the invariants that keep it in its role. Load when creating or editing a module document in docs/code/, or adding a package under src/"
type: "meta"
scope: "global"
---

# Module Rule Document Template

**MANDATORY structure for ALL `docs/code/module-*.md` documents**

A `module-*` document defends one package's single responsibility. It states the one reason the package
changes, the one role the package plays in the architecture, where the boundary to its neighbours runs, and the
invariants a change must keep for the package to stay in that role. It is written for someone who has new code
in hand and must decide which package it goes in, and for a reviewer deciding whether a change fits.

## Why a Package Has a Rule Document

[code.md §1](code.md#1-core-principles) sends a fact about one module into that module's docstring. A package's
responsibility is different, because a reader applies it to code that is not yet in the package. They are
choosing which package to open, so a docstring inside that package is read too late. A boundary also concerns
the neighbouring packages, since it says what does not belong here and where that code goes instead.

The package's own `__init__.py` docstring still describes what the package holds. The module document states
what may enter it. It does not repeat the docstring, and it lists none of the package's modules, classes or
functions: that would be an inventory, and inventories rot.

## Naming and Scope

One document per package. Its name is `module-` followed by the package's full import path, with dots and
underscores turned into hyphens. A document for a subpackage extends its parent's document by name, so the
two sort together:

| Package | `name` | `scope` |
|---|---|---|
| `lorecraft.vfs` | `module-lorecraft-vfs` | `pkg:lorecraft.vfs` |
| `lorecraft.project.syntax` | `module-lorecraft-project-syntax` | `pkg:lorecraft.project.syntax` |

Every package in the layers contract of `pyproject.toml` has a module document. A subpackage gets one when it
has a boundary of its own worth defending against its siblings. Otherwise its parent's document covers it.

## Structure

Every module rule document contains the following sections in order.

### Frontmatter (required)

| Field | Value | Notes |
|-------|-------|-------|
| `name` | `module-<import-path-hyphenated>` | Matches filename minus `.md`, and spells the same path as `scope` |
| `description` | Discovery-optimized summary | Names the package; the `Load when` clause names adding or moving code in it |
| `type` | `"pkg"` | Always |
| `scope` | `"pkg:<import.path>"` | The package's full import path, starting with the import package |

The check verifies the form of `name` and `scope`, but not that they spell the same path. A reader verifies
that by hand. See [code.md §2](code.md#2-frontmatter-requirements) for field rules.

### Header

#### Title (required)

H1 of the form "The `<import.path>` Package".

#### Scope line (omitted)

**No scope line.** `scope` already names the package.

### Body

#### Responsibility (required)

One sentence stating the package's responsibility, without "and". Follow it with the one reason the package
changes. A responsibility that needs "and" is two packages, or one package with a co-location that this section
must justify: a shared invariant, an ordering, or a lifetime that cannot be split.

#### Role (required)

The one role the package plays, named in bold, from the role vocabulary that the corpus's architecture rules
define. Follow it with what that role means for this package specifically, and nothing more about the role in
general: the architecture document owns that, and this section links it as `Foundation`.

#### Belongs Here (required)

The tests a reader applies to new code to decide that it belongs in this package. State them as conditions on
the code ("reads the disk", "is a pure function of one document's text"), not as a list of what exists today.

#### Belongs Elsewhere (required)

A table of the code a reader is tempted to put here, and the package it goes in instead:

```markdown
| Code that… | Belongs in |
|---|---|
| {{a test on the code, one line}} | `{{lorecraft.neighbour}}` |
```

Each row is a pointer to the neighbour, not a restatement of its rules: the neighbour's own module document
holds the full statement.

#### Invariants (required)

The conditions a change must keep for the package to stay in its role. Each one can be verified against a diff:
what the package may import, read, cache, hold and hand upward. An invariant is stated once, where the code that
can break it lives: one only this package's code can break lives here, and one any package can break lives in the
architecture document and is not restated here. An invariant the layers contract or a type
already enforces is stated once, as a reason, not as a checklist item. Use a bulleted list.

#### Examples (required)

At least one Bad/Good pair, at most three, Bad first. Each Bad example is code that a plausible change puts into
the wrong package, or that pushes the package out of its role. Each Good example is the same intent placed
correctly. See [code.md §6](code.md#6-content-guidelines) for how an example is written.

### Footer

#### Checklist (required)

Each item is an invariant or a placement test, phrased so that it can be checked against a diff.

#### References (required)

- The architecture document the Role section names, as `Foundation`.
- Each architecture document the package's invariants build on, as `Foundation`.
- `principle-single-responsibility`, as `Foundation`.
- The parent package's module document, as `Extends`, for a subpackage.

See [code.md §4](code.md#4-cross-reference-rules) for relationship types and direction rules.

## Template

```markdown
---
name: "module-{{import-path-hyphenated}}"
description: "The {{import.path}} package's responsibility, role, boundary and invariants. Load when adding or moving code in {{import.path}}, or deciding whether code belongs there"
type: "pkg"
scope: "pkg:{{import.path}}"
---

# The `{{import.path}}` Package

## Responsibility

{{One sentence, no "and". Then the one reason it changes.}}

## Role

**{{Role}}.** {{What the role means for this package.}}

## Belongs Here

- {{A test on new code}}

## Belongs Elsewhere

| Code that… | Belongs in |
|---|---|
| {{A test on new code}} | `{{lorecraft.neighbour}}` |

## Invariants

- {{A condition verifiable against a diff}}

## Examples

{{Bad/Good pairs. See Structure > Examples.}}

## Checklist

- [ ] {{Verification item}}

## References

- [{{architecture-document}}]({{architecture-document}}.md) - Foundation: {{The role vocabulary}}
- [principle-single-responsibility](principle-single-responsibility.md) - Foundation: One reason to change
```

## References

- [code](code.md) - Extends: Base code rules documentation format specification
