---
name: "python-paths"
description: "Filesystem path values, resolved containment checks, and stable directory order. Load when accepting a path, checking whether it belongs under a root, or discovering files"
type: "core"
scope: "global"
---

# Filesystem Paths

A filesystem path stays a `Path`, or a domain type backed by `Path`, while code joins, inspects, or traverses
it. Convert it to text only at a boundary that requires text, such as a report field. This document owns path
identity and discovery order.
Reading file contents is owned by the code at the I/O boundary; exception selection is owned by
[python-exceptions](python-exceptions.md).

## 1. Keep Filesystem Paths as `Path` Values

Accept and return `Path` or a `Path`-backed domain type for filesystem locations. Joining with `/`, reading
`name` or `suffix`, and asking whether a path exists then use one consistent interface. A string path invites
manual separator handling and makes it easy to confuse a report label with a location that can be opened.

```python
# ❌ Bad — string joining assumes a separator and returns a display label as a location
def schema_location(root: str, name: str) -> str:
    return root + '/schemas/' + name
```

```python
# ✅ Good — the result remains a filesystem location for the caller
def schema_location(root: Path, name: str) -> Path:
    return root / 'schemas' / name
```

## 2. Resolve Both Paths Before Checking Containment

Resolve the candidate and the allowed root before calling `is_relative_to()`. Without resolution, the check
compares path components without accounting for `..` or symbolic links. Use `strict=True` when the candidate
must already exist, so a missing input fails at the boundary rather than during a later read.

```python
# ❌ Bad — lexical containment can accept a path whose resolved target lies elsewhere
def belongs_to_corpus(candidate: Path, root: Path) -> bool:
    return candidate.is_relative_to(root)
```

```python
# ✅ Good — both sides describe their resolved locations before comparison
def belongs_to_corpus(candidate: Path, root: Path) -> bool:
    return candidate.resolve(strict=True).is_relative_to(root.resolve(strict=True))
```

This check describes the paths at the time of resolution. Code that must defend against concurrent changes to
the filesystem needs a stronger file-opening strategy; path comparison alone does not provide one.

## 3. Sort Discovered Paths When Order Is Observable

Sort paths returned from directory traversal before using them to produce findings, reports, or other ordered
output. `iterdir()`, `glob()`, and `rglob()` do not promise a stable order. Sorting at the point where order
becomes part of the result keeps repeated runs comparable.

```python
# ❌ Bad — report order changes with filesystem traversal order
def schema_files(root: Path) -> list[Path]:
    return list(root.glob('*.json'))
```

```python
# ✅ Good — callers receive a stable sequence
def schema_files(root: Path) -> list[Path]:
    return sorted(root.glob('*.json'))
```

## Checklist

Before committing code, verify:

- [ ] Filesystem locations in changed signatures and return values are `Path` or `Path`-backed domain types,
      with text conversion only at a text-only boundary
- [ ] A containment check resolves both candidate and root; an existing input uses `strict=True`
- [ ] Directory results that determine output order are sorted before they are returned or reported

## References

- [python-exceptions](python-exceptions.md) - Related: Owns the error raised when a path is missing or invalid
- [pattern-resource-lifecycle](pattern-resource-lifecycle.md) - Related: Owns acquisition and release of open
  filesystem resources

## External References

- [Python `pathlib` documentation](https://docs.python.org/3.12/library/pathlib.html)
- [Real Python: Python's pathlib Module](https://realpython.com/python-pathlib/)
