---
name: "pattern-memoization"
description: "Cache a result only when its meaning is fixed by the key for the cache's whole lifetime, with a chosen bound and owner. Load when adding functools.cache, lru_cache or cached_property, when a lookup is repeated, or when a cached result can go stale"
type: "core"
scope: "global"
---

# Memoization (Stable Results Only)

## Rule

Cache a result only when the key fully determines it for as long as the cache lives. Before adding a cache,
answer three questions at the spot:

1. **Is the result stable?** A function of its arguments alone, with no side effect and no hidden input such as
   a file's contents, the clock or the environment. Reading a file is a hidden input: a cache keyed on its path
   returns stale content once the file changes, which a watch mode guarantees it will.
2. **Is the returned value safe to share?** Every caller receives the same object. Return an immutable value (a
   frozen dataclass, a tuple, a `frozenset`, a `MappingProxyType`), never a `dict` or `list` a caller can
   mutate for everyone else.
3. **Who owns the lifetime?** `functools.lru_cache` and `functools.cache` hold every argument and result until
   evicted or cleared. Bound them with `maxsize` unless the key space is small and closed. A cache on a method
   keys on `self`, keeping every instance alive for the process; cache per instance with
   `functools.cached_property` or a dictionary the instance owns.

When the hidden input matters, make it part of the key (a path together with its modification time) or give
the cache to an object whose lifetime matches the input's validity, such as one check run.

## Examples

1. **Caching a hidden input and a mutable result**

```python
# ❌ Bad — a schema edited during a watch session is never re-read, and one check that adds a
# default to the returned dict changes the schema for every later check.
@cache
def load_schema(path: Path) -> dict[str, object]:
    return json.loads(path.read_text())
```

```python
# ✅ Good — the cache lives as long as one run, and callers share an immutable value.
class SchemaCache:
    def __init__(self) -> None:
        self._loaded: dict[Path, HeaderSchema] = {}

    def get(self, path: Path) -> HeaderSchema:
        if path not in self._loaded:
            self._loaded[path] = HeaderSchema.parse(path.read_text())
        return self._loaded[path]
```

2. **Caching a method**

```python
# ❌ Bad — the cache keys on `self`, so every workspace ever built stays in memory.
class Workspace:
    @lru_cache(maxsize=None)
    def documents(self) -> tuple[Path, ...]:
        return tuple(sorted(self.root.rglob('*.md')))
```

```python
# ✅ Good — the value lives and dies with its instance.
class Workspace:
    @cached_property
    def documents(self) -> tuple[Path, ...]:
        return tuple(sorted(self.root.rglob('*.md')))
```

```python
# 🔶 Acceptable — a module-level cache for a pure parse over a closed, small key space.
@cache
def parse_corpus_name(stem: str) -> CorpusName:
    return CorpusName.parse(stem)
```

## Why It Matters

A cache is a copy of an answer, and a copy that outlives its truth returns wrong results with no error.
Mutable shared results turn one caller's local change into global state. Unbounded or method-level caches keep
objects alive invisibly, which appears as memory growth in long-running modes rather than as a failure.

## Pragmatism Caveat

Do not cache what is cheap to recompute; a cache adds a lifetime to reason about. Measure or reason about the
repeated cost before adding one. A value computed once and passed down needs no cache at all.

## Checklist

- [ ] The cached result depends only on the key for the cache's lifetime
- [ ] Hidden inputs (file contents, time, environment) are part of the key or bound the cache's lifetime
- [ ] Cached values are immutable
- [ ] `lru_cache` has a `maxsize`, unless the key space is small and closed
- [ ] No `lru_cache` or `cache` decorates a method; per-instance values use `cached_property`

## References

- [pattern-value-object](pattern-value-object.md) - Related: Immutable values are safe to share from a cache
- [pattern-repository](pattern-repository.md) - Related: A repository may own a read cache scoped to its lifetime

## External References

- [Python docs — `functools.lru_cache`](https://docs.python.org/3.12/library/functools.html#functools.lru_cache)
- [Python docs — `functools.cached_property`](https://docs.python.org/3.12/library/functools.html#functools.cached_property)
- [Python FAQ — How do I cache method calls?](https://docs.python.org/3.12/faq/programming.html#how-do-i-cache-method-calls)
