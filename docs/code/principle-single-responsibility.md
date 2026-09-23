---
name: "principle-single-responsibility"
description: "Single Responsibility — one class, one reason to change; split when it spans external systems or mixes I/O with pure computation. Load when designing classes, splitting modules, or reviewing types that do both"
type: "principle"
scope: "global"
---

# Single Responsibility Principle (SRP)

## Rule

A class or module owns one responsibility. Split when any of these observable signals is present:

1. **Multiple external systems**: the methods touch several distinct outside worlds (the filesystem, a JSON
   Schema validator, a subprocess, a report sink). Each boundary is its own concern. Three is a strong
   signal; two warrants a split when they change independently.
2. **Disjoint attribute access**: the methods partition into groups that touch non-overlapping sets of
   attributes. The groups are separate classes sharing an `__init__` by coincidence.
3. **Mixed I/O and transformation**: the same unit both performs effects (read a file, shell out, write a
   report) and does pure computation (parsing frontmatter, planning an outline, formatting a finding).
   Extract the pure part — it is the part worth unit testing, and effects make that impossible.

When a signal fires, split into focused units and compose them.

## Examples

1. **One concern per module in a package**
   A corpus checker is four modules, each with exactly one job: a registry (which format spec governs which
   corpus, is it declared), a reader (one document, one parse), a cache (one compiled schema per spec,
   compiled lazily, cleared together), and the adapter that exposes the cache to the checking pipeline.

```python
# ❌ Bad — one class owns the spec registry, the schema compilation, the parsing, and the pipeline surface.
# Signals 1 and 2 both fire: it touches the filesystem + the schema store + the checker protocol, and
# `_specs`/`_declared` are never read by the same methods that read `_validators`/`_open_docs`.
class CorpusService:
    def __init__(self, specs: list[SpecRef]) -> None:
        self._specs = specs
        self._declared: dict[str, bool] = {}
        self._validators: dict[str, Validator] = {}
        self._open_docs: dict[str, int] = {}

    def is_declared(self, corpus: str) -> bool: ...

    def spec_for(self, corpus: str) -> SpecRef | None: ...

    def compile(self, spec: SpecRef) -> Validator: ...

    def documents(self, corpus: str, pattern: str) -> list[Document]: ...

    def parse(self, raw: str) -> Document: ...

    def shutdown(self) -> None: ...
```

```python
# ✅ Good — four units, each describable in one sentence, composed by the caller.

# The registry module — "which format spec governs this corpus, and is it declared"
def spec_for(corpus: str) -> SpecRef | None: ...


def is_declared(spec: SpecRef) -> bool: ...


# The reader module — "one document, one parse"
class DocumentReader:
    @classmethod
    def open(cls, path: Path) -> 'DocumentReader': ...

    def read(self) -> Document: ...


# The cache module — "one compiled schema per spec, compiled lazily, cleared together"
class SchemaCache:
    def validator_for(self, spec: SpecRef) -> Validator: ...

    def clear(self) -> None: ...


# The checker module — "expose the cache to the checking pipeline"
class CachedSchemas:
    def __init__(self, cache: SchemaCache) -> None:
        self._cache = cache
```

2. **Separate the pure transformation from the effect**
   Reporting over-budget sections splits in two: one function does the file and sink I/O, another is a pure
   sectioning function. Only the pure one holds the tricky invariant (sections are cut on heading
   boundaries, and a `#` inside a fenced code block is not a heading), and only the pure one can be unit
   tested directly.

```python
# ❌ Bad — the sectioning rule is trapped inside the I/O. Testing "a section never starts
# inside a fenced code block" now requires a document tree on disk, and the first version of
# this cut a section at every line beginning with '#' — each comment in a fenced example
# became a phantom heading, correct documents were reported over budget, and no test could
# have caught it.
def report_sections(sink: ReportSink, path: Path) -> list[Finding]:
    emitted: list[Finding] = []
    current: list[str] = []
    for line in path.read_text(encoding='utf-8').splitlines():
        if line.startswith('#') and current:
            if len(current) > LINE_BUDGET:
                emitted.append(sink.emit(over_budget(current)))
            current = []
        current.append(line)
    if len(current) > LINE_BUDGET:
        emitted.append(sink.emit(over_budget(current)))
    return emitted
```

```python
# ✅ Good — the effect is a thin shell over a pure core.
def plan_sections(lines: list[str]) -> list[range]:
    """Cut ``lines`` into sections on heading boundaries.

    A ``#`` inside a fenced code block is a comment, not a heading, and never opens a section.

    Args:
        lines: The document body, in file order.

    Returns:
        Half-open index ranges, one per section, covering every line exactly once.
    """
    # pure: list in, ranges out — tested with a list literal, no document on disk


def report_sections(sink: ReportSink, path: Path) -> list[Finding]:
    """Emit one finding per section that exceeds the line budget.

    Args:
        sink: Report sink the findings are written to.
        path: Rule document to read.

    Returns:
        The emitted findings, in section order.

    Raises:
        ReportError: If the sink rejects a finding.
    """
    lines = path.read_text(encoding='utf-8').splitlines()
    over = [span for span in plan_sections(lines) if len(span) > LINE_BUDGET]
    return [sink.emit(over_budget(lines[span.start : span.stop])) for span in over]
```

## Why It Matters

A class with one responsibility has one reason to change. A schema cache changing how it compiles cannot
break frontmatter parsing, because it does not contain any. A registry gaining a corpus cannot break the
document reader.

The testability consequence is concrete: anything fused to an effect can only be exercised by laying out a
tree of real document files and running the checker over it — so the cases that are awkward to set up end up
untested, and the ones that are set up are slow enough to skip in the edit loop. Separable pure logic is
tested with a list and an assertion, in milliseconds, at the point of the change.

## Pragmatism Caveat

Small classes that touch two systems are not automatically wrong. A reader that owns both the parsed
document and its source lines is one concern, because the whole point of the class is the coupling between
them (every finding must carry the line it came from) — splitting them would put the invariant in neither
half. A checker owns its schema cache because the cache's lifetime _is_ the checker's lifetime.

When a signal fires and you keep the concerns together, say why in the module docstring or a comment (a
shared invariant, an ordering guarantee, a lifetime that cannot be split). An undocumented violation is
always wrong.

## Checklist

Before committing code, verify:

- [ ] Each class or module can be described in one sentence without "and"
- [ ] No class both performs I/O and holds a non-trivial pure algorithm — the algorithm is a module-level function
- [ ] Attributes partition into one cohesive group, not two groups touched by disjoint method sets
- [ ] A change to one concern (spec registry, frontmatter schema, lifecycle) touches one module
- [ ] Deliberate co-location of concerns is explained in the module docstring

## References

- [principle-law-of-demeter](principle-law-of-demeter.md) - Related: Overloaded types are the ones callers end
  up navigating through

## External References

- [SOLID: The Single Responsibility Principle (Uncle Bob)](https://blog.cleancoder.com/uncle-bob/2014/05/08/SingleReponsibilityPrinciple.html)
- [SOLID Principles in Python (Real Python)](https://realpython.com/solid-principles-python/)
