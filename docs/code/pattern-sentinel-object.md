---
name: "pattern-sentinel-object"
description: "A unique object distinguishes an omitted value from a supplied value, including None. Load when None is meaningful input but an API must also detect omission or a cache must distinguish a miss from a stored None"
type: "core"
scope: "global"
---

# Sentinel Object (Omission by Identity)

## Rule

Use a private sentinel when `None` is a valid value and code must also recognize that no value was supplied.
Create one stable object for the boundary and compare with `is`. Keep it private so callers do not need to
construct or guess it. An omitted argument, a supplied `None`, and a supplied value must each retain their
own meaning through the operation.

Use `None` directly when it already means omission. For a mapping key, use `key in mapping` when presence is
all that matters. A sentinel earns its place when an API needs a default distinct from every valid value,
including `None`, or when a cached result may itself be `None`.

## Examples

An update accepts `None` to clear a summary and omission to leave it alone:

```python
# ❌ Bad — both omission and an explicit None leave the old summary unchanged.
def update_summary(current: str | None, incoming: str | None = None) -> str | None:
    if incoming is None:
        return current
    return incoming
```

```python
# ✅ Good — identity marks omission, leaving None available to mean clear.
_MISSING = object()


def update_summary(current: str | None, incoming: str | None | object = _MISSING) -> str | None:
    if incoming is _MISSING:
        return current
    if incoming is None:
        return None
    if not isinstance(incoming, str):
        raise TypeError('summary must be text or None')
    return incoming
```

## Why It Matters

Overloading `None` makes it impossible to express both omission and an intentional null value. A distinct
object keeps those cases separate at runtime. Identity comparison also avoids colliding with a legitimate
value whose equality behavior is unusual or expensive.

## Pragmatism Caveat

Do not introduce a sentinel when `None` is not a valid supplied value, or when `key in mapping` states the
question directly. Do not send an identity sentinel across process or serialization boundaries: the
receiver will not have the same object. Use an explicit tagged value for such a boundary.

## Checklist

- [ ] Omission and a supplied `None` genuinely need different behavior
- [ ] One private sentinel object is reused at the boundary and tested with `is`
- [ ] The sentinel cannot escape as a valid domain result
- [ ] Serialized or cross-process data uses an explicit representation instead of object identity
- [ ] A simpler `None` check or mapping membership test would not express the required distinction

## References

- [principle-least-surprise](principle-least-surprise.md) - Foundation: An omitted argument and an explicit value retain their stated meanings
- [python-fn](python-fn.md) - Related: Default arguments and explicit absence at a function boundary

## External References

- [Python Design Patterns — Sentinel Object](https://python-patterns.guide/python/sentinel-object/)
- [Real Python — object and sentinel values](https://realpython.com/ref/builtin-types/object/)
