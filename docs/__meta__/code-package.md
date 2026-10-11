---
name: "code-package"
description: "Structure template for `docs/code/package-*.md` code specs, one per package, each stating what the package is for, whether it is built and published, which packages may import it and which it may import, and the invariants that keep it so. Load when creating or editing a package document in docs/code/, or adding a package to the repository"
type: "meta"
scope: "global"
---

# Package Code Spec Template

**MANDATORY structure for ALL `docs/code/package-*.md` documents**

A `package-*` document defends the line between the repository's packages: which one is built and published,
which ones are private, and which way imports may run between them. It is written for someone adding code or a
package who must decide where it goes and what it may import, and for a reviewer deciding whether a
change crosses that line.

## Why a Package Has a Code Spec Beside Its Module Specs

A [code-module](code-module.md) document defends one layer inside the import package: what may enter it, and
which neighbouring layer takes the rest. A package is the level above. Its question is not which layer holds a
piece of code, but whether the code ships at all, and which package may import which. A private package such as
a generator is not a layer of the import package, so a module document cannot describe it.

The package's `__init__.py` docstring describes what it holds, and each layer's module document states what may
enter a layer. A package document repeats neither.

## Naming and Scope

One document per package that has its own `pyproject.toml`. Its name is `package-` followed by the package's
name, and its `scope` is the top-level import package it governs:

| Document | `name` | `scope` |
|---|---|---|
| The published package | `package-lorecraft` | `pkg:lorecraft` |
| The private generation package | `package-lorecraft-gen` | `pkg:lorecraft_gen` |

Code that is not a package of its own, such as the test tiers, is described by the document of the package whose
code it exercises.

## Structure

Every package code spec contains the following sections in order.

### Frontmatter (required)

| Field | Value | Notes |
|-------|-------|-------|
| `name` | `package-<name>` | Matches filename minus `.md` |
| `description` | Discovery-optimized summary | Names the package; the `Load when` clause names adding code to it or a package beside it |
| `type` | `"pkg"` | Always |
| `scope` | `"pkg:<import_package>"` | A top-level import package, in snake_case |

See [code.md §2](code.md#2-frontmatter-requirements) for field rules.

### Title (required)

H1 of the form "The `<import_package>` Package".

### Responsibility (required)

One sentence stating what the package is for, followed by the one reason it
changes.

### Publication (required)

Whether the package is built and published. A published package states what the release builds from it. A
private package states that it is never built or published, and what keeps it out of an artifact.

### Boundary (required)

A table of the packages it sits beside, with the direction in which each may import the other and what enforces
that direction: an import-linter contract, another gate, or review where no gate exists.

### Invariants (required)

The conditions a change must keep, each verifiable against a diff: what the package ships, imports, restates and
configures. Use a bulleted list.

### Examples (required)

At least one Bad/Good pair, at most three, Bad first. Each Bad example is code or configuration that a plausible
change puts into the wrong package. See [code.md §6](code.md#6-content-guidelines) for how an example is written.

### Checklist (required)

Each item is an invariant or a placement test, phrased so that it can be checked against a diff.

### References (required)

- The architecture documents the invariants build on, as `Foundation`.
- `principle-single-responsibility`, as `Foundation`.
- The sibling package document, as `Companion`.

See [code.md §4](code.md#4-cross-reference-rules) for relationship types and direction rules.

### External References (optional)

Links to the outside sources the package's packaging rests on.

## Template

```markdown
---
name: "package-{{name}}"
description: "The {{name}} package's responsibility, publication and import boundary. Load when adding code to {{name}}, or deciding whether code belongs in it or in a package beside it"
type: "pkg"
scope: "pkg:{{import_package}}"
---

# The `{{import_package}}` Package

## Responsibility

{{One sentence, then the one reason it changes.}}

## Publication

{{Built and published, or never built or published, and what keeps it so.}}

## Boundary

| Package | It may import this package | This package may import it | Enforced by |
|---|---|---|---|
| `{{neighbour}}` | {{Yes or No}} | {{Yes or No}} | {{A contract, a gate, or review}} |

## Invariants

- {{A condition verifiable against a diff}}

## Examples

{{Bad/Good pairs. See Structure > Examples.}}

## Checklist

- [ ] {{Verification item}}

## References

- [principle-single-responsibility](principle-single-responsibility.md) - Foundation: One reason to change
```

## References

- [code](code.md) - Extends: Base code corpus meta spec
