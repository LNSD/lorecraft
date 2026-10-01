---
name: "python-fn-conv"
description: "Conversion and constructor names: as_ for a cheap view, to_ for an independent value, from_/parse_/load_/build_ for construction, and with_ or dataclasses.replace for a modified copy. Load when naming a conversion, an alternate constructor, or a method that derives a changed copy"
type: "core"
scope: "global"
---

# Conversions and Constructors

**A conversion's name says what it costs and whether the result shares anything with its source.** The
vocabulary follows the Rust API Guidelines where Python itself is inconsistent (`asdict` copies,
`fromisoformat` drops the underscore), with the parts that need ownership dropped because Python cannot keep
them.

Parameter kinds and defaults are owned by [python-fn](python-fn.md). Every other function name is owned by
[python-fn-names](python-fn-names.md). Unchecked constructors are owned by
[python-fn-unchecked](python-fn-unchecked.md). This document is about the names that convert and construct.

## 1. `as_` Is a Cheap View, `to_` Builds an Independent Value

`as_x()` re-presents the receiver: constant cost, no I/O, cannot fail, and the result may alias the receiver,
the way `numpy.asarray` returns an array unchanged and `PurePath.as_posix` re-renders a path. `to_x()` does
work and returns a new value that shares nothing mutable with the receiver, so changing the result never
changes the source. `into_` is not used: Python cannot spend a receiver, so the Rust promise is unkeepable.

The split tells a caller what may go inside a loop. A `to_` name in a hot path is a visible cost; an `as_`
name that copies a large structure is a hidden one.

```python
# ❌ Bad — reads as a free view, re-serializes the whole outline on every call
def as_json(self) -> str:
    return json.dumps([heading.to_dict() for heading in self._headings])
```

```python
# ✅ Good — the cost is in the name, and the free view is named for what it shares
def to_json(self) -> str:
    return json.dumps([heading.to_dict() for heading in self._headings])


def as_tuple(self) -> tuple[Heading, ...]:
    return self._headings
```

## 2. Construction Says Its Source: `from_`, `parse_`, `load_`

An alternate constructor is a `@classmethod` named `from_<source>` returning `Self`, one source shape each:
`from_heading`, `from_bytes`. A module function turning text into a value with no I/O is `parse_<thing>`; one
that reads storage first is `load_<thing>`. `build_` assembles a composite from parts. `of_`, `make_`,
`new_`, and `create_` without a side effect are not used, because `__init__` already is the primary
constructor and a second vocabulary for the same act tells the reader nothing.

The source in the name is what lets a caller tell, at the call site, whether `parse_document(text)` can touch
the disk. It cannot; `load_document(path)` does.

## 3. A Modified Copy Is `with_<field>` or `dataclasses.replace`

A frozen value changes by returning a copy. When the change is one named field the type exposes, the method
is `with_<field>(value)`, like `PurePath.with_suffix`; otherwise callers use `dataclasses.replace`. A frozen
type never has `set_<field>`, and a `with_` method revalidates the invariant the constructor checks, because
a copy that skips validation is an unchecked constructor under another name.

```python
# ✅ Good — the original is untouched, and the copy goes through the same validation
def with_budget(self, budget: int) -> Self:
    return dataclasses.replace(self, budget=budget)
```

## Checklist

Before committing code, verify:

- [ ] Every `as_` name is constant-cost, does no I/O, and cannot fail; every `to_` result shares nothing
      mutable with its receiver; no name starts with `into_`
- [ ] Alternate constructors are `from_<source>` classmethods returning `Self`; text-to-value functions are
      `parse_`, I/O-backed ones `load_`; no `of_`, `make_`, or `new_` constructor is added
- [ ] Frozen types change through `with_<field>` or `dataclasses.replace`, never `set_<field>`, and a `with_`
      method revalidates

## References

- [python-fn](python-fn.md) - Extends: Owns parameter kinds and defaults of the functions named here
- [python-fn-names](python-fn-names.md) - Related: Owns predicates, effects, accessors, lookups, and the
  lifecycle pair
- [python-fn-unchecked](python-fn-unchecked.md) - Related: Owns the `_unchecked` constructor and its proof
- [pattern-value-object](pattern-value-object.md) - Related: Owns the invariant a `with_` copy revalidates
- [principle-least-surprise](principle-least-surprise.md) - Foundation: Why a name that hides its cost is a
  defect

## External References

- [Rust API Guidelines: Ad-hoc conversions follow `as_`, `to_`, `into_` conventions](https://rust-lang.github.io/api-guidelines/naming.html#ad-hoc-conversions-follow-as_-to_-into_-conventions-c-conv)
- [NumPy: `numpy.asarray`](https://numpy.org/doc/stable/reference/generated/numpy.asarray.html)
- [Python `copy.replace`](https://docs.python.org/3/library/copy.html#copy.replace)
