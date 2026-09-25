---
name: "pattern-type-dispatch"
description: "Select an operation's implementation by the runtime type of its first argument with functools.singledispatch. Load when one operation handles several unrelated input types, when an isinstance chain keeps growing, or when choosing between match, a registry and singledispatch"
type: "core"
scope: "global"
---

# Type Dispatch (Implementation per Input Type)

## Rule

When one operation has an independent implementation for each of several unrelated input types, and the runtime
type is genuinely what selects the implementation, declare the operation with `functools.singledispatch` and
register one implementation per type. Each implementation is a separate function that can be read and tested
alone, and adding a type adds a registration instead of editing a branch.

The base function is the fallback. Make it explicit: raise `TypeError` naming the unsupported type, rather than
returning a default that hides a missing registration. Register with the parameter annotation
(`@operation.register` on a function whose first parameter is annotated) so the dispatched type and the
signature cannot disagree. Use `functools.singledispatchmethod` for the method form.

Choose the selection mechanism by what actually selects the behavior:

| Selected by | Use |
|---|---|
| A small closed set of shapes, in one place | `match` or an `if` chain |
| A public name | a registry ([pattern-registry](pattern-registry.md)) |
| A capability the caller provides | a `Protocol` ([pattern-protocol](pattern-protocol.md)) |
| The runtime type of the first argument, open to new types | `singledispatch` |

## Examples

Findings carry values of several types that must become JSON for the report.

```python
# ❌ Bad — every new value type edits this chain, and an unknown type silently becomes a string
# in the report instead of failing the test that added it.
def to_json_value(value: object) -> JsonValue:
    if isinstance(value, Path):
        return value.as_posix()
    elif isinstance(value, Enum):
        return value.value
    elif isinstance(value, CorpusName):
        return str(value)
    return str(value)
```

```python
# ✅ Good — one implementation per type, and an explicit failure for a type nobody registered.
@singledispatch
def to_json_value(value: object) -> JsonValue:
    raise TypeError(f'no JSON form for {type(value).__name__}')


@to_json_value.register
def _(value: Path) -> JsonValue:
    return value.as_posix()


@to_json_value.register
def _(value: Enum) -> JsonValue:
    return value.value
```

## Why It Matters

A growing `isinstance` chain puts unrelated logic in one function and hides the fallback at the bottom, where a
silent default absorbs types nobody considered. Dispatch keeps each type's logic separate, makes the unsupported
case loud, and lets a module that defines a new type register its own implementation beside it.

## Pragmatism Caveat

Two or three cases handled in one place read better as `match`. Dispatch on type is wrong when the selecting key
is a name, a flag or a capability. Do not use `singledispatch` to simulate method overriding on classes you own;
put the method on the class.

## Checklist

- [ ] `singledispatch` is used only where the runtime type of the first argument selects the behavior
- [ ] The base implementation raises `TypeError` naming the unsupported type
- [ ] Implementations register through the parameter annotation
- [ ] A small closed set of cases uses `match` instead
- [ ] Name- or capability-keyed selection uses a registry or a protocol instead

## References

- [pattern-registry](pattern-registry.md) - Related: Selection by public name rather than by type
- [pattern-protocol](pattern-protocol.md) - Related: Selection by capability rather than by type
- [principle-least-surprise](principle-least-surprise.md) - Foundation: An unsupported type fails loudly

## External References

- [Python docs — `functools.singledispatch`](https://docs.python.org/3.12/library/functools.html#functools.singledispatch)
- [PEP 443 — Single-dispatch generic functions](https://peps.python.org/pep-0443/)
- [Python docs — The `match` statement](https://docs.python.org/3.12/reference/compound_stmts.html#the-match-statement)
