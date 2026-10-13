---
name: "python-frozenset"
description: "Immutable sets and membership-only collections as `frozenset`, the `frozenset[T]` annotation on fields and signatures, and where a `tuple` stays because its order is read. Load when declaring a constant or field that holds a set of values, writing an `in` test against a literal, or choosing between `set`, `frozenset` and `tuple`"
type: "core"
scope: "global"
---

# Immutable Sets (`frozenset`)

**A collection that is built once and asked only whether it holds a value is a `frozenset`.** `set` says "this
grows or shrinks", `tuple` says "the order is read", and a reader takes each at its word; `frozenset` is the
one that says the values are a fixed group with no order.

The `Final` annotation that goes with a module constant is owned by
[python-constants](python-constants.md). The record fields that hold a set are declared as
[python-dataclasses](python-dataclasses.md) owns. This document is about when a set is a `frozenset`.

## 1. A Set Built Once Is a `frozenset`

A set that nothing changes after it is built is a `frozenset`: a module constant, a field of a frozen record,
or a value a registry hands out. The type, not the author's intent, is what stops a later caller from adding
to it.

A mutable `set` held in a shared place is a global that any caller can grow, and the next caller then sees
the change. `frozenset` is hashable as well, so it can be a dictionary key or a member of another set.

```python
# ❌ Bad — a `set` field on a frozen record; `frozen=True` stops rebinding the field, and one
# caller's `.add('draft')` changed the statuses every later check accepted
@dataclass(frozen=True, slots=True)
class StatusPolicy:
    accepted: set[str]
```

```python
# ✅ Good — the record cannot be changed through its field
@dataclass(frozen=True, slots=True)
class StatusPolicy:
    accepted: frozenset[str]
```

A function that fills a local `set` and returns it as a `frozenset` is right as it stands: the `set` does not
outlive the call. A mutable cache a class fills over its life, such as `self._seen: set[Path]`, is state and
stays a `set`.

## 2. A Collection Only Tested With `in` Is a `frozenset`

A literal tuple or list that is used only on the right of `in` is a `frozenset`, named once as a constant when
it is used at more than one place or when the name explains it. The membership test is what it states, and a
`tuple` there suggests an order that nothing reads.

```python
# ❌ Bad — a tuple, so a reader looks for the place the order matters; there is none
if extension in ('.md', '.markdown', '.mdx'):
    return parse_markdown(path)
```

```python
# ✅ Good — the type says the group is only asked about
_MARKDOWN_EXTENSIONS: Final[frozenset[str]] = frozenset({'.md', '.markdown', '.mdx'})

if extension in _MARKDOWN_EXTENSIONS:
    return parse_markdown(path)
```

The right of `in` must be a collection of values. A `str` there is a substring test, so a string of characters
is not swapped for a `frozenset` of them where the empty string or a longer one is a valid left side.

## 3. Annotate a Read-Only Set as `frozenset[T]` or `AbstractSet[T]`

A field, a return type and a constant that hold an immutable set are annotated `frozenset[T]`, so the checker
rejects `.add()` at the call site. A parameter that only reads a set may take `AbstractSet[T]`, which accepts a
`set` and a `frozenset` alike, and a parameter is never annotated `set[T]` when it is not mutated.

```python
# ❌ Bad — `set[str]` promises the callee may change it, so the caller copies defensively
def is_known(name: str, known: set[str]) -> bool:
    return name in known
```

```python
# ✅ Good — the signature says it only reads
def is_known(name: str, known: AbstractSet[str]) -> bool:
    return name in known
```

## 4. A `tuple` Stays Where Its Order Is Read

A collection stays a `tuple` when something reads its order: it is iterated to build output, joined into a
message, compared for equality as a sequence, or reported as a list of problems. A `frozenset` iterates in an
order that changes between runs, so replacing such a `tuple` moves the output.

A `frozenset` that must be listed is sorted at the point it is listed, with a key that gives a total order, so
the output does not depend on how the set was built.

```python
# ❌ Bad — the message names the fields in whatever order the set holds them, so a snapshot
# of the diagnostic changes from one run to the next
message = ', '.join(missing_fields)
```

```python
# ✅ Good — the order is read, so it is made explicit where it is read
message = ', '.join(sorted(missing_fields))
```

## Checklist

Before committing code, verify:

- [ ] A set built once, in a constant, a frozen record or a returned value, is a `frozenset`, not a `set`
- [ ] A literal tuple or list that is only tested with `in` is a `frozenset`, and a `str` on the right of `in`
      is left as it is
- [ ] Fields, return types and constants are annotated `frozenset[T]`, and a read-only parameter is
      `AbstractSet[T]`, not `set[T]`
- [ ] A `tuple` stays where its order is iterated, joined or reported, and a `frozenset` that is listed is
      sorted where it is listed

## References

- [python-constants](python-constants.md) - Related: Owns the `Final[T]` annotation and the immutable value
  behind a constant name
- [python-dataclasses](python-dataclasses.md) - Related: Owns how a frozen record declares its fields
- [python-typing](python-typing.md) - Related: Owns the spelling of builtin generics in an annotation

## External References

- [Python docs — `frozenset`](https://docs.python.org/3/library/stdtypes.html#frozenset)
- [Python docs — `collections.abc.Set`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Set)
