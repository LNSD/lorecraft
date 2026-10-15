---
name: "module-lorecraft-jsonschema"
description: "The lorecraft.jsonschema package's responsibility, role, boundary and invariants: the JSON Schema vocabulary, dialect and validator seam. Load when adding or moving code in lorecraft.jsonschema, reading JSON Schema library errors, or importing jsonschema or referencing"
type: "pkg"
scope: "pkg:lorecraft.jsonschema"
---

# The `lorecraft.jsonschema` Package

## Responsibility

Provide a stable, Lorecraft-owned vocabulary for the JSON Schema facts the project uses. It changes when the
dialect or the facts Lorecraft reads from a validator change.

## Role

**Derivation.** It turns validator reports into Lorecraft-owned facts that project code can use without depending
on validator records. The dialect and keyword vocabulary stay with that translation because they define its input
and output, letting one import contract contain both third-party libraries.

## Belongs Here

- The accepted JSON Schema dialect and the JSON types named by its `type` keyword.
- Typed values for keywords Lorecraft reads from validation errors.
- The adapter that reads `jsonschema` or `referencing` values and turns them into Lorecraft-owned facts.
- The public vocabulary imported by callers from `lorecraft.jsonschema`.

## Belongs Elsewhere

| Code that… | Belongs in |
|---|---|
| Reads a structure file or decides which schema it declares | `lorecraft.project` |
| Reports problems found in a frontmatter value | `lorecraft.project` |
| Words a diagnostic or decides whether a problem is reported | `lorecraft.rules` |
| Provides generic immutable values | `lorecraft.core` |

## Invariants

- The layers contract places this package beside `lorecraft.yaml`, above `lorecraft.core`; neither package imports the other.
- This package imports only `lorecraft.core` from Lorecraft, so it can be used below `lorecraft.project` without a cycle.
- `project`, `rules` and `cli` may import this package's public vocabulary; this inbound use is separate from third-party library containment.
- `jsonschema` and `referencing` are imported only here. A temporary exception remains for
  `lorecraft.project.schemas.frontmatter_schema` while its validator seam is moved.
- No library type escapes the package boundary; callers receive Lorecraft-owned vocabulary and facts.
- Validation returns problems as values and raises nothing for an invalid instance.
- `format` remains annotation-only; validation does not assert format semantics.
- Schema error messages are retained verbatim as opaque `message` text when no typed keyword fact applies.

## Examples

```python
# ❌ Bad — a caller dispatches on a validator's string keyword and accepts its untyped value
if error.validator == 'type':
    expected = error.validator_value
```

```python
# ✅ Good — a caller consumes the typed keyword owned by the boundary
match keyword_of(error):
    case TypeKeyword(names):
        return names
    case _:
        return ()
```

## Checklist

Before committing code, verify:

- [ ] Only `lorecraft.jsonschema` imports `jsonschema` or `referencing`, apart from the temporary frontmatter schema seam
- [ ] This package imports no Lorecraft package above `lorecraft.core`
- [ ] No third-party validator or reference-library type escapes through the public API
- [ ] Invalid instances produce problem values and validation raises nothing
- [ ] `format` does not assert semantics during validation
- [ ] Unclassified validator prose is preserved verbatim as an opaque message

## References

- [adr-001-snapshot-model](../arch/adr-001-snapshot-model.md) - Foundation: Defines the Derivation role this package plays
- [principle-single-responsibility](principle-single-responsibility.md) - Foundation: One package responsibility, one reason to change
