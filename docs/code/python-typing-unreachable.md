---
name: "python-typing-unreachable"
description: "Unreachable code: the `Never` bottom type, `-> Never` on a function that always raises, `match` closed by `assert_never` over a closed union or enum, `case _` only over an open domain, and `raise AssertionError` where ty cannot prove a branch dead. Load when writing a function that never returns, branching on which member of a union or enum a value holds, writing a `case _` or final `else`, or ending a path the checker cannot see is dead"
type: "core"
scope: "global"
---

# Unreachable Code

**A branch the code claims cannot run is either proved dead by `ty` or fails loudly the moment it runs.** The
first is the default and costs nothing at runtime: the checker narrows a value until its type is `Never`, and
a call that accepts only `Never` type-checks only where no value can arrive. The second is for the dead
branches the checker cannot see, and it raises rather than returning a placeholder. What goes wrong is a
branch that is silently live: a catch-all arm that absorbs a member added later, or a dummy `return` that
hands a caller a value nobody meant.

How an annotation is spelled, and when it is written at all, is owned by [python-typing](python-typing.md).
This document is about the paths an annotation says no value takes.

## 1. Spell the Bottom Type `Never`, Never `NoReturn`

The bottom type, the type with no values, is written `Never`, imported from `typing`. `NoReturn` means the
same to the checker, but it names only one of the places the type appears, a return, and reads wrong as the
parameter of `assert_never` or the narrowed type of a variable. One spelling means a reader never wonders
whether the two differ.

A function that always raises is annotated `-> Never`. The checker then treats every line after a call to it
as unreachable, so the caller narrows through the call and needs no placeholder `return` after it. Annotated
`-> None`, the same helper tells the checker the caller continues, and the caller's return type is violated on
a path that does not exist.

```python
# ❌ Bad — `-> None` says the call returns, so ty reports `load_spec` as able to return None, and the dummy
# `return` added to silence it hands a caller an empty spec if `reject` ever stops raising
def reject(path: RootRelativePath, detail: str) -> None:
    raise InvalidSpecError(path, detail)


def load_spec(path: RootRelativePath, data: object) -> StructureSpec:
    if not isinstance(data, dict):
        reject(path, 'the specification must be a JSON object')
        return StructureSpec.empty()
    return StructureSpec.from_mapping(data)
```

```python
# ✅ Good — `-> Never` ends the path at the call, and `data` is narrowed to dict after it
def reject(path: RootRelativePath, detail: str) -> Never:
    raise InvalidSpecError(path, detail)


def load_spec(path: RootRelativePath, data: object) -> StructureSpec:
    if not isinstance(data, dict):
        reject(path, 'the specification must be a JSON object')
    return StructureSpec.from_mapping(data)
```

## 2. Branch on a Closed Union With `match` and `assert_never`

Code that decides by which member a closed union holds — an error variant's `source`, a parse outcome, a plain
data union — uses `match` with one class pattern per member and closes with `case _: assert_never(value)`,
imported from `typing`. It is the tool whenever a union is branched on, never an `isinstance` chain.

The closing arm is what makes the `match` a check. Once every member has an arm, the value's type there is
`Never` and the call type-checks; when a member is added to the union and not handled, `ty` reports the arm,
through a union nested in another and an attribute such as `exc.source` alike. An `isinstance` chain ending in
a fall-through gives the new member whatever the last branch does, and nothing says so. The arm is written even
where every other arm returns and the return type would already catch the gap: a `match` is exhaustive by what
it says, not by what its function happens to return.

```python
# ❌ Bad — a block kind added to the union falls through to the paragraph branch and is counted as prose
def words(block: Block) -> int:
    if isinstance(block, CodeFence):
        return 0
    return len(block.text.split())
```

```python
# ✅ Good — a member with no arm is a type error at the assert_never call
def words(block: Block) -> int:
    match block:
        case CodeFence():
            return 0
        case Heading() | Paragraph():
            return len(block.text.split())
        case _:
            assert_never(block)
```

A union of classes is the one exception, because a class pattern matches an instance and never a class: a value
typed `type[A] | type[B]` has no `match` to branch with. A branch on which class it is, as with a rule's
declaration, is an `issubclass` chain closed by `else: assert_never(value)`, which `ty` narrows the same way, and
a comment at the chain says why it is not a `match`, so the next editor does not convert it.

```python
# ✅ Good — a class pattern cannot match a class, so the branch on a declaration's kind is an `issubclass`
# chain, closed by `assert_never` so a third kind of declaration is a type error here
def is_in_service(declaration: type[Rule] | type[RemovedRule]) -> bool:
    if issubclass(declaration, Rule):
        return True
    elif issubclass(declaration, RemovedRule):
        return False
    else:
        assert_never(declaration)
```

## 3. A Catch-All Arm Handles Only an Open Domain

A `case _:` or a final `else` that does something is a real case, and it is written only where the matched
value comes from an open domain: a `str`, an `int`, an `errno`, an error type string a library reports. There
the catch-all names what the rest of the domain means, such as "any other refusal".

A closed domain — a union, an `Enum`, a `Literal` — has no rest. Its catch-all is `assert_never`, and every
member, enum members included, gets its own arm. A catch-all with behaviour over a closed domain is exactly
the fall-through [§2](#2-branch-on-a-closed-union-with-match-and-assert_never) forbids: the member added next
year takes it, and `ty` has nothing to report.

```python
# ❌ Bad — `Severity.NOTE` was added later and was rendered as an error, failing every run that emitted one
def exit_code(severity: Severity) -> int:
    match severity:
        case Severity.WARNING:
            return 0
        case _:
            return 1
```

```python
# ✅ Good — each member is decided; a new one is a type error until someone decides it too
def exit_code(severity: Severity) -> int:
    match severity:
        case Severity.WARNING:
            return 0
        case Severity.ERROR:
            return 1
        case _:
            assert_never(severity)
```

```python
# ✅ Good — an errno is an open domain, so the catch-all is a real classification
def classify(error: OSError) -> Refusal:
    match error.errno:
        case errno.ENOENT:
            return Refusal.NOT_FOUND
        case _:
            return Refusal.OTHER
```

## 4. A Branch `ty` Cannot Prove Dead Raises `AssertionError`

Some paths are dead for a reason the type system cannot express: an infinite iterator, an invariant a
validator established upstream. The path ends with `raise AssertionError('unreachable: <why>')`, the message
naming the invariant that makes it dead.

The two neighbouring forms are wrong for opposite reasons. `assert_never` there is a type error, because the
checker cannot prove the value `Never`, and silencing that error defeats every other `assert_never` the reader
trusts. `assert False` is removed under `python -O`, so the dead path returns `None` after all, and Ruff's
`B011` reports it. The converse also holds: where `ty` can prove the path dead, write `assert_never`, because
an `AssertionError` there gives up the check.

```python
# ❌ Bad — `-> int` is broken on a path ty sees, and the `return 0` added to satisfy it would name a slot
# that is already taken
def first_free_slot(taken: set[int]) -> int:
    for slot in itertools.count(1):
        if slot not in taken:
            return slot
    return 0
```

```python
# ✅ Good — the path ty cannot rule out ends the run instead of returning a wrong slot
def first_free_slot(taken: set[int]) -> int:
    for slot in itertools.count(1):
        if slot not in taken:
            return slot
    raise AssertionError('unreachable: itertools.count() never stops')
```

## Checklist

Before committing code, verify:

- [ ] No `NoReturn` in the diff; the bottom type is written `Never`
- [ ] Every function that raises on every path is annotated `-> Never`, and no placeholder `return` follows a
      call to one
- [ ] Every branch on which member a closed union holds is a `match` closed by `case _: assert_never(...)`,
      never an `isinstance` chain, even where the return type would already catch a missing member; over a union
      of classes, which no class pattern matches, it is an `issubclass` chain closed by
      `else: assert_never(...)`, with a comment saying why
- [ ] Every `case _:` or final `else` with behaviour matches a value from an open domain; over a union, an
      `Enum`, or a `Literal`, each member has an arm and the catch-all is `assert_never`
- [ ] Every path dead for a reason `ty` cannot see ends in `raise AssertionError('unreachable: ...')` naming
      the reason, never `assert False`, a dummy `return`, or an `assert_never` with a silenced diagnostic

## References

- [python-typing](python-typing.md) - Extends: Owns how the annotations that make a path provably dead are
  spelled and checked
- [error-types](error-types.md) - Related: Owns the error unions whose `source` a `match` most often branches on
- [error-handling](error-handling.md) - Related: Owns the handler that catches a variant before its `source`
  is matched

## External References

- [Typing guide: Unreachable Code and Exhaustiveness Checking](https://typing.python.org/en/latest/guides/unreachable.html)
- [`typing.assert_never`](https://docs.python.org/3/library/typing.html#typing.assert_never)
- [`typing.Never`](https://docs.python.org/3/library/typing.html#typing.Never)
