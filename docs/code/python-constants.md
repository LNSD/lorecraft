---
name: "python-constants"
description: "Module-level constants: the `Final[T]` annotation, the explicit type inside it, and immutable values behind a `Final` name. Load when declaring or reviewing a module-level constant, a lookup table, or a value computed once at import"
type: "core"
scope: "global"
---

# Module Constants (`Final`)

**A module constant is a binding the checker refuses to rebind, holding a value nobody can mutate.**
`SCREAMING_SNAKE` only asks a reader not to reassign a name; `Final[T]` makes `ty` enforce it, and an immutable
value closes the second door that `Final` leaves open.

The casing of a constant is owned by [python-naming](python-naming.md), which also owns class-level
`ClassVar` constants. The comment that explains why a constant has its value is owned by
[python-docstrings](python-docstrings.md). This document is about module-level constants.

## 1. Annotate Every Module Constant `Final[T]`

Every module-level name whose value is fixed once the module is imported is annotated `Final[T]`, private
constants and values computed at import included. A table built by a function call at import is as constant as
a literal, and the annotation says so.

A plain annotation lets any module rebind the name, and a test that patches it, or an assignment that meant to
shadow it locally, changes the value for every caller in the process. `Final` turns that rebinding into a
`just typecheck` failure.

```python
# ❌ Bad — nothing stops a later `MAX_HEADING_DEPTH = 6` in a helper from changing the
# limit for every checker in the run; the casing asked, and nobody enforced it
MAX_HEADING_DEPTH: int = 4
```

```python
# ✅ Good — a rebinding anywhere is a type error before the change is merged
from typing import Final

MAX_HEADING_DEPTH: Final[int] = 4
_SPEC_SUFFIX: Final[str] = '.structure.json'
CHECKERS_BY_ASPECT: Final[Mapping[str, Checker]] = index_checkers(CHECKERS)
```

## 2. Spell the Type Inside `Final`

Write `Final[str]`, never a bare `Final`. A bare `Final` asks the checker to infer the type, and it infers the
narrowest one: `Literal['.md']` rather than `str`, the exact tuple shape rather than `tuple[str, ...]`.

The inferred type is a claim nobody wrote. A function that accepts the constant today starts rejecting a caller
the day the literal changes, and the reader has to evaluate the value to learn the type the module promises.

```python
# ❌ Bad — the type is whatever the value happens to be, so widening this list to a
# fourth aspect changes the declared type of every signature that took it
SPEC_ASPECTS: Final = ('header', 'structure', 'budget')
```

```python
# ✅ Good — the contract is stated, and the value can grow without changing it
SPEC_ASPECTS: Final[tuple[str, ...]] = ('header', 'structure', 'budget')
```

## 3. A `Final` Name Holds an Immutable Value

`Final` forbids rebinding the name, not mutating the value. A constant collection is a `tuple`, a `frozenset`, or
a `Mapping` backed by `types.MappingProxyType`, never a `list`, `set`, or `dict`, and the annotation names the
read-only type so the checker rejects a mutation at the call site as well.

A `Final` list is a shared mutable global with a reassuring annotation: one caller appends, and every other
caller sees the change for the rest of the process.

```python
# ❌ Bad — `Final` held, and the list still grew: one command appended `.txt` to skip
# notes, and every later check in the process ignored them too
IGNORED_SUFFIXES: Final[list[str]] = ['.swp', '.tmp']
```

```python
# ✅ Good — neither the name nor the value can change after import
IGNORED_SUFFIXES: Final[frozenset[str]] = frozenset({'.swp', '.tmp'})
CORPUS_TITLES: Final[Mapping[str, str]] = MappingProxyType({'code': 'Code Rules', 'feat': 'Features'})
```

A module-level collection that is meant to change, such as a registry filled as modules import, is state rather
than a constant, and it is not annotated `Final`. The registry's shape is owned by
[pattern-registry](pattern-registry.md).

## Checklist

Before committing code, verify:

- [ ] Every new or changed module-level constant, private and computed ones included, is annotated `Final[...]`
- [ ] No `Final` is bare; the type inside the brackets is spelled out
- [ ] Every `Final` collection is a `tuple`, `frozenset`, or `MappingProxyType`, annotated with a read-only type,
      and no mutable module-level registry is annotated `Final`

## References

- [python-typing](python-typing.md) - Related: The spelling of the type written inside `Final[...]`
- [python-naming](python-naming.md) - Related: `SCREAMING_SNAKE` casing, and class-level `ClassVar` constants
- [python-docstrings](python-docstrings.md) - Related: The comment that states why a constant has its value
- [pattern-registry](pattern-registry.md) - Related: The mutable module-level registry that is not a constant

## External References

- [PEP 591 - Adding a final qualifier to typing](https://peps.python.org/pep-0591/)
