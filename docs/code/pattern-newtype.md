---
name: "pattern-newtype"
description: "Static distinctions for values with the same representation and no runtime invariant. Load when same-typed domain values must not be interchanged"
type: "core"
scope: "global"
---

# NewType (Static Distinction)

## Rule

Use `typing.NewType` when two values share a runtime representation but mean different things, and neither
needs runtime validation or behavior. The type checker then rejects accidental substitutions while values
remain their original primitive at runtime.

`NewType` is not a wrapper or validator. Calling `CorpusName(raw)` returns `raw` unchanged; it does not check
the string, create a distinct runtime object, or protect against untyped callers. Validate external data at
the boundary. When a value needs a runtime invariant or its own behavior, use a frozen value object instead
([pattern-value-object](pattern-value-object.md)).

Create the `NewType` at the boundary where a plain value takes on its domain meaning. Annotate the functions
that consume the domain value with the new type, and pass it through without converting back to the primitive.
Use one alias for each meaning; do not create a `NewType` when the distinction cannot prevent a realistic mix-up.

## Examples

Two names may both be strings but occupy distinct roles in a signature. Keep those roles visible to the type
checker:

```python
# ❌ Bad — both arguments are strings, so swapping corpus and document compiles.
def schema_path(corpus: str, document: str) -> str:
    return f'docs/__meta__/{corpus}-{document}.header.json'


schema_path('code', 'python-guide')
```

```python
# ✅ Good — the arguments carry distinct static types, so a swap is a type error.
from typing import NewType

CorpusName = NewType('CorpusName', str)
DocumentName = NewType('DocumentName', str)


def schema_path(corpus: CorpusName, document: DocumentName) -> str:
    return f'docs/__meta__/{corpus}-{document}.header.json'


corpus = CorpusName('code')
document = DocumentName('python-guide')
schema_path(corpus, document)
```

## Why It Matters

A `NewType` lets a static checker distinguish domain roles without adding a runtime wrapper. It catches
transposed same-typed arguments at the call site, while keeping simple values cheap to construct and easy to
pass to APIs that accept the underlying type.

## Pragmatism Caveat

Do not use `NewType` to claim that a value has been validated. Its constructor is a runtime identity function,
so malformed input remains malformed. Use a value object when construction must establish an invariant,
provide operations, or make runtime inspection meaningful. Leave ordinary values as their primitive when
there is no plausible confusion.

## Checklist

- [ ] The new type distinguishes values with the same representation and genuinely different meanings
- [ ] Construction happens where the plain value takes on its domain meaning
- [ ] Any runtime validation is performed separately at the untrusted input boundary
- [ ] Functions that consume the domain value annotate it with the `NewType`
- [ ] A value object is used instead when the type must enforce an invariant or own behavior

## References

- [pattern-value-object](pattern-value-object.md) - Related: Runtime invariants and behavior on wrapped primitives

## External References

- [Python docs — `typing.NewType`](https://docs.python.org/3/library/typing.html#newtype)
- [ty — Type system](https://docs.astral.sh/ty/features/type-system/)
