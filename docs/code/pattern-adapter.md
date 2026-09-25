---
name: "pattern-adapter"
description: "Translate a third-party object's shape into the small contract a consumer needs, at the boundary. Load when a library returns data, raises errors, or names operations differently from what domain code expects, or when library types start appearing in domain signatures"
type: "core"
scope: "global"
---

# Adapter (Translate at the Boundary)

## Rule

When an external object nearly fits what a consumer needs but differs in method names, argument types, return
shape or exceptions, translate it in one place at the boundary. Domain code receives domain values and domain
exceptions; it never branches on a library's enum, unpacks a library's tuples, or catches a library's errors.

An adapter exposes only the operations its consumer uses. It is not a complete wrapper of the library: a method
nobody calls is a second copy of the library's surface that must be kept in sync for no reader.

A function is the default adapter. Reach for a class only when the adapter must hold state across calls or
satisfy a consumer that expects an object with methods. A `Protocol` describes the consumer's contract when
several implementations serve it; a single adapter does not need one. `@runtime_checkable` checks that
attributes exist, not that signatures or behavior match, so an `isinstance` check against a protocol does not
prove an adapter works.

Translate failures as well as values. The adapter catches the library's exceptions and raises the domain's,
chained with `raise ... from exc`, so the consumer handles one vocabulary of errors.

## Examples

1. **Translating a library's value shape**
   A watcher reports changes as the library's `set[tuple[Change, str]]`; the check run needs domain paths.

```python
# ❌ Bad — the rerun logic unpacks library tuples and compares library enums, so a library
# upgrade that adds a change kind breaks domain code that never imported the library on purpose.
def documents_to_recheck(batch: set[tuple[Change, str]], root: Path) -> set[Path]:
    touched = set()
    for change, raw in batch:
        if change != Change.deleted:
            touched.add(Path(raw).relative_to(root))
    return touched
```

```python
# ✅ Good — one function translates the library shape; the rerun logic reads domain values only.
def to_path_changes(batch: set[tuple[Change, str]], root: Path) -> list[PathChange]:
    """Translate a watch batch into changes relative to the workspace root."""
    return [
        PathChange(path=Path(raw).relative_to(root), removed=change is Change.deleted)
        for change, raw in batch
    ]


def documents_to_recheck(changes: list[PathChange]) -> set[Path]:
    return {change.path for change in changes if not change.removed}
```

2. **Translating a library's failure**
   A parser raises its own error type; the header check reports frontmatter defects as findings.

```python
# ❌ Bad — every caller catches the parser library's exception, so replacing the parser means
# editing every check that reads frontmatter.
def check_header(text: str) -> list[Finding]:
    try:
        data = parse_frontmatter(text)
    except ParserError as exc:
        return [Finding(message=str(exc))]
    return validate(data)
```

```python
# ✅ Good — the adapter raises the domain exception; checks depend on it alone.
def read_frontmatter(text: str) -> Mapping[str, object]:
    """Parse a frontmatter block.

    Raises:
        FrontmatterError: If the block is not valid.
    """
    try:
        return parse_frontmatter(text)
    except ParserError as exc:
        raise FrontmatterError(f'invalid frontmatter: {exc}') from exc
```

## Why It Matters

A library's shape that leaks into domain code spreads its upgrade cost across every module that touched it. One
translation point means one place to change, one place to test the mapping, and one place to test the failure
translation. Domain signatures stay readable without knowing the library, and tests of domain logic build
domain values directly instead of faking library types.

## Pragmatism Caveat

Do not wrap a library whose types already are the domain's vocabulary: `pathlib.Path`, `re.Pattern` and
standard containers need no adapter. Do not write an adapter for a call made in exactly one place; that call is
already the boundary. Do not mirror a library's whole API to have "our own" version of it.

## Checklist

- [ ] Library-specific types, enums and exceptions do not appear in domain signatures
- [ ] Translation of values and errors happens in one place per library seam
- [ ] The adapter exposes only operations its consumer uses
- [ ] Library exceptions are re-raised as domain exceptions with `raise ... from exc`
- [ ] A function is used unless the adapter must hold state or satisfy an object-shaped contract
- [ ] No `isinstance` check against a `runtime_checkable` protocol stands in for testing the adapter

## References

- [principle-information-hiding](principle-information-hiding.md) - Foundation: The library's shape is a decision hidden behind the adapter
- [pattern-protocol](pattern-protocol.md) - Related: Describes the consumer's contract when several adapters serve it
- [pattern-facade](pattern-facade.md) - Related: A facade coordinates a workflow; an adapter translates one interface
- [python-exceptions](python-exceptions.md) - Related: Declares the domain exceptions an adapter raises

## External References

- [Python Patterns Guide — Composition Over Inheritance](https://python-patterns.guide/gang-of-four/composition-over-inheritance/)
- [Python docs — `typing.runtime_checkable`](https://docs.python.org/3.12/library/typing.html#typing.runtime_checkable)
