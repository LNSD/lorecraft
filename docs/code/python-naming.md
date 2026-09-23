---
name: "python-naming"
description: "What a symbol is called: PEP 8 casing, the leading-underscore privacy boundary, predicate and verb prefixes, the connect/disconnect lifecycle pair, capability constants, and repr versus str. Load when naming a module, class, function, attribute, or constant, or when adding a dunder"
type: "core"
scope: "global"
---

# Symbol Names

A name is the only part of an implementation every caller reads. It has to say the category of thing (class,
constant, private helper), whether touching it costs anything, and whether it answers a question or performs
an action — before the reader opens the body. Where this project has settled on a local vocabulary that
differs from the standard library's, **the local vocabulary wins**, because a convention applied everywhere is
worth more than a better convention applied half the time.

What the named things are annotated with is owned by [python-typing](python-typing.md). Where a module or
package name may live is owned by [python-modules](python-modules.md). Exception class naming sits with
[python-exceptions](python-exceptions.md).

## 1. Case Follows PEP 8

| Construct | Form | Example |
|-----------|------|---------|
| Module, package | `lower_snake` | `frontmatter`, `section_outline` |
| Class, exception, `TypeVar`, `Protocol` | `PascalCase` | `OutlineChecker`, `TDocument` |
| Function, method, attribute, local | `lower_snake` | `check_document`, `_pending_findings` |
| Module-level constant | `SCREAMING_SNAKE` | `DEFAULT_LINE_BUDGET` |
| Type alias | `PascalCase` | `HeadingPath = tuple[str, ...]` |

There is nothing to argue about here; the value is that the case alone tells a reader whether a bare name in a
call is a class being constructed or a function being applied.

Two additions the table does not cover: a single leading underscore is the privacy marker (§2), never a
trailing one except to dodge a keyword (`class_`, `id_`); and abbreviations keep one case (`JsonSchema`,
`parse_url`, never `parseURL` or `JSONSchema`).

## 2. A Leading Underscore Is the Privacy Boundary

A name with one leading underscore is internal to its class or module: nothing outside may read it, call it,
or depend on its existence. A name without one is a contract, and changing its signature or deleting it is a
breaking change.

Python does not enforce this, which is exactly why it must be applied without exception. An attribute that
outside code reaches into becomes part of the interface whether or not anyone intended it, and the next person
to rename it discovers the dependency at runtime in someone else's module.

```python
# ❌ Bad — the finding buffer and the section counter read as public API, so a caller that
# pokes `checker.pending.append(finding)` bypasses the severity filter and a warnings-only
# report ships with an error in it
class OutlineChecker:
    def __init__(self, spec: OutlineSpec) -> None:
        self.spec = spec
        self.pending: list[Finding] = []
        self.sections_seen = 0
```

```python
# ✅ Good — the boundary is visible: `spec` is contract, the buffer is not
class OutlineChecker:
    def __init__(self, spec: OutlineSpec) -> None:
        self.spec = spec
        self._pending: list[Finding] = []
        self._sections_seen = 0
```

Double leading underscores (name mangling) are not used. They do not add privacy over a single underscore and
they make a subclass's override silently fail to override.

## 3. Predicates Read `is_`/`has_`/`supports_`, Effects Read Verb-First

A function or attribute that answers a yes/no question is named for the question and returns `bool`:
`is_connected`, `has_pending_findings`, `supports_autofix`, `section_exists`. A function that does something
opens with the verb: `check_document`, `flush`, `register_checker`, `rewind_to`.

The prefix is a cost signal as much as a grammar rule. A reader who meets `is_stale` in an `if` assumes it is
a cheap inspection; if the name is a verb, they assume something changed. Crossing the two hides a write
inside a condition, or makes a pure check look like it needs a comment.

```python
# ❌ Bad — reads as a question, answers with a side effect. Anyone calling it twice in
# a condition registers the heading twice, and the outline report then carries a
# duplicate-section finding the document does not contain
def check_section(self, heading: str) -> bool:
    if heading not in self._known_sections:
        self._register_section(heading)
    return True
```

```python
# ✅ Good — the question and the action are two names, and a caller can ask without
# changing anything
def section_exists(self, heading: str) -> bool:
    return heading in self._known_sections


def ensure_section(self, heading: str, spec: SectionSpec) -> None:
    if not self.section_exists(heading):
        self._register_section(heading, spec)
```

`supports_` is reserved for a capability question about the implementation itself (`supports_autofix`), as
opposed to `is_`/`has_` about the current state of an instance.

## 4. `connect`/`disconnect` Is the Lifecycle Pair

A component that holds an external resource opens it with `connect()` and releases it with `disconnect()`.
Not `open`/`close`, not `start`/`stop`, not `connect`/`close`.

The standard library's pair is `close`, and choosing otherwise is deliberate. This project spells the pair
`connect`/`disconnect` everywhere, and a mixed vocabulary is worse than either consistent choice: a reader who
has to remember which of two names a given component uses checks the source every time, and a generic teardown
path that calls one of them silently skips the components that spell it the other way. The symmetry of the
pair is the point — `disconnect` is visibly the inverse of `connect` in a way `close` is not.

```python
# ❌ Bad — three vocabularies for one lifecycle. A shared teardown helper can only call
# one of them, so the components spelling it differently hold their handles until the
# process exits
class CorpusSource:
    def connect(self) -> None: ...
    def close(self) -> None: ...


class SchemaRegistry:
    def open(self) -> None: ...
    def shutdown(self) -> None: ...
```

```python
# ✅ Good — one pair, so a caller holding an unknown component knows both halves
class CorpusSource:
    def connect(self) -> None: ...
    def disconnect(self) -> None: ...


class SchemaRegistry:
    def connect(self) -> None: ...
    def disconnect(self) -> None: ...
```

Both are idempotent: `connect` on an open component is a no-op, and `disconnect` on a closed one does not
raise. The context-manager protocol that wraps the pair belongs to
[pattern-resource-lifecycle](pattern-resource-lifecycle.md).

## 5. Class-Level Capability Constants Are `SCREAMING_SNAKE`

A constant that declares what an implementation can do — the document types it accepts, whether it can rewrite
what it finds, its maximum report size — is a class attribute in `SCREAMING_SNAKE`, annotated `ClassVar`.

Casing is what separates a fact about the class from a fact about the instance. `self.supports_autofix`
suggests something that could differ between two checkers of the same type or change once a document has been
read; `SUPPORTS_AUTOFIX` says it is a property of the implementation, fixed at import.

```python
# ❌ Bad — set per instance, so a registry inspecting the class before construction
# cannot read it, and the value is constructible into a lie
class OutlineChecker(Checker[OutlineSpec]):
    def __init__(self, spec: OutlineSpec) -> None:
        super().__init__(spec)
        self.supported_types = {DocumentType.RULE}
        self.supports_autofix = False
```

```python
# ✅ Good — readable off the class, so a corpus can be routed to its checkers before any
# of them is built
class OutlineChecker(Checker[OutlineSpec]):
    SUPPORTED_TYPES: ClassVar[set[DocumentType]] = {DocumentType.RULE, DocumentType.SKILL}
    SUPPORTS_AUTOFIX: ClassVar[bool] = False
```

## 6. `__repr__` Is Unambiguous, `__str__` Is for Humans

`__repr__` either round-trips — output that could be pasted back to rebuild the object — or names the type
along with whatever identifies this instance. `__str__` is a sentence for a person, and is omitted entirely
when `__repr__` already reads well enough.

**Nothing ever parses `__str__` output.** A status line, a progress summary, a report footer: these are built
for a human's eye and are free to change wording at any time. Code that extracts a number or a state from one
of them is depending on a sentence, and it breaks the first time someone improves the phrasing — silently,
with a parse that still succeeds against the wrong field.

```python
# ❌ Bad — repr hides the identity, so a list of these in a traceback is a wall of
# indistinguishable object addresses; and the caller has resorted to parsing the
# human-facing string, which breaks the day the word "documents" becomes "files"
class CheckProgress:
    def __str__(self) -> str:
        return f'Checked {self.documents} documents in {self.corpus} ({self.elapsed:.1f}s)'


completed = int(str(progress).split()[1])
```

```python
# ✅ Good — repr identifies the instance; the count is read from the attribute that
# exists for that purpose, and the sentence stays free to change
class CheckProgress:
    def __repr__(self) -> str:
        return f'CheckProgress(corpus={self.corpus!r}, documents={self.documents})'

    def __str__(self) -> str:
        return f'Checked {self.documents} documents in {self.corpus} ({self.elapsed:.1f}s)'


completed = progress.documents
```

Where a caller needs structured status, the object exposes attributes or returns a `dict` — never a string to
be taken apart.

## 7. No `get_` Prefix on a Plain Accessor

An accessor that reads state already held returns it under the name of the thing: `heading_count`, `schema`,
`corpus`. `get_` is reserved for a lookup that does work — a read from disk, a network call, a cache miss that
computes.

Keeping the prefix meaningful makes it informative. If every read is `get_`, the prefix says nothing and a
reader cannot tell `get_outline()` (a stored attribute) from `get_outline()` (a re-read and re-parse of the
file). If only the expensive ones carry it, the name is a warning.

```python
# ❌ Bad — the prefix is noise on both, so nothing distinguishes the free read from the
# one that re-reads the file; a caller puts the second inside a per-section loop
def get_corpus(self) -> str:
    return self._corpus


def get_heading_count(self) -> int:
    return len(parse_outline(self._path.read_text(encoding='utf-8')))
```

```python
# ✅ Good — the bare name is free, the `fetch_` name costs a read and a parse
@property
def corpus(self) -> str:
    return self._corpus


def fetch_heading_count(self) -> int:
    return len(parse_outline(self._path.read_text(encoding='utf-8')))
```

A stored value with no computation is a `@property` or a plain attribute, not a method: `document.corpus`,
not `document.corpus()`.

## Checklist

Before committing code, verify:

- [ ] Every new module, class, function, attribute, and constant matches the casing table, and no name uses
      double leading underscores
- [ ] Every attribute and helper not part of the contract has a single leading underscore, and nothing outside
      the owning class or module reads an underscored name
- [ ] Every `bool`-returning function reads as a question (`is_`/`has_`/`supports_`/`_exists`) and performs no
      mutation; every function that mutates opens with a verb
- [ ] A component holding an external resource spells its lifecycle `connect`/`disconnect`, and both are safe
      to call twice
- [ ] Capability declarations are `SCREAMING_SNAKE` `ClassVar` class attributes, not instance attributes set
      in `__init__`
- [ ] Every class with a `__str__` also has a `__repr__` that names its type and identity, and no code in the
      diff parses, splits, or matches against a `__str__` result
- [ ] No `get_` prefix on an accessor that only returns stored state; those are properties or bare attributes

## References

- [principle-least-surprise](principle-least-surprise.md) - Foundation: Why a name that contradicts its cost
  or its effect is a defect
- [principle-information-hiding](principle-information-hiding.md) - Foundation: The boundary the leading
  underscore marks
- [pattern-resource-lifecycle](pattern-resource-lifecycle.md) - Related: The acquire/release protocol behind
  the `connect`/`disconnect` pair
- [python-typing](python-typing.md) - Related: The annotations these names carry, including `ClassVar`
- [python-modules](python-modules.md) - Related: Where a module of a given name may be placed
- [python-exceptions](python-exceptions.md) - Related: Choosing bases for exception classes
- [python-docstrings](python-docstrings.md) - Related: The docstring that follows the name

## External References

- [PEP 8 - Naming Conventions](https://peps.python.org/pep-0008/#naming-conventions)
- [Python Data Model - `object.__repr__`](https://docs.python.org/3/reference/datamodel.html#object.__repr__)
