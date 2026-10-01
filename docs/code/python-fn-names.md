---
name: "python-fn-names"
description: "What a function or method name promises: is_/has_/supports_ predicates, verb-first effects and mutators returning None, no get_ on a plain accessor, find_ versus a raising lookup, iter_ versus a materialized sequence, idempotent ensure_, reject_ guards, and the connect/disconnect lifecycle pair. Load when naming a function or method, or reviewing what a name promises"
type: "core"
scope: "global"
---

# Function Names

**A function name is a contract about cost, effect, and failure, and a caller is entitled to rely on it
without reading the body.** Each prefix below carries one meaning, and a name that breaks its prefix's promise
is a defect in the name, not in the caller. Where this project has settled on a vocabulary that differs from
the standard library's, the local vocabulary wins, because a convention applied everywhere is worth more than
a better convention applied half the time.

Parameter kinds and defaults are owned by [python-fn](python-fn.md). Casing and the privacy underscore are
owned by [python-naming](python-naming.md). Conversion and constructor names are owned by
[python-fn-conv](python-fn-conv.md). This document is about what the rest of a function's name commits to.

## 1. Predicates Read `is_`/`has_`/`supports_` and Change Nothing

A function or attribute that answers a yes/no question is named for the question and returns `bool`:
`is_connected`, `has_pending_findings`, `supports_autofix`, `section_exists`. Asking never changes state.
`supports_` is reserved for a capability of the implementation itself, as opposed to `is_`/`has_` about the
current state of an instance.

The prefix is a cost signal as much as a grammar rule. A reader who meets `is_stale` in an `if` assumes a
cheap inspection; a predicate that writes hides an effect inside a condition.

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

## 2. Effects Read Verb-First, and a Mutator Returns `None`

A function that does something opens with the verb: `check_document`, `flush`, `register_checker`. A method
that changes its receiver returns `None`. A function returning a changed value leaves its input alone and is
named for the result: `sorted`, `reversed`, `merged_findings`.

This is the standard library's own rule, given in the Python design FAQ for `list.sort`: a returned value
would invite `findings = findings.sort()` and chains that hide which object changed. No mutator returns `self`,
and no function chooses between the two with an `inplace=` flag, which pandas is removing for the same reason.

## 3. No `get_` Prefix on a Plain Accessor

An accessor that reads state already held returns it under the name of the thing: `heading_count`, `schema`,
`corpus`. `get_` is reserved for a lookup that does work — a read from disk, a network call, a cache miss that
computes.

Keeping the prefix meaningful makes it informative. If every read is `get_`, the prefix says nothing and a
reader cannot tell a stored attribute from a re-read and re-parse of the file. If only the expensive ones
carry it, the name is a warning.

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

A stored value with no computation is a `@property` or a plain attribute, not a method.

## 4. The Name Says What Absence Does

A lookup that may find nothing is named `find_<thing>` and returns `X | None`. A lookup that must succeed
raises, and is named for the thing, under [§3](#3-no-get_-prefix-on-a-plain-accessor), or `require_<thing>`
where a `find_` sibling exists. A tolerant twin of a raising lookup is `<name>_or_none`, as in SQLAlchemy's
`one`/`one_or_none`. `try_` is not used: the `| None` return already says it, and a second marker can
disagree with the annotation.

```python
# ❌ Bad — `find_` promises a None the caller checks for, and raises instead
def find_section(self, heading: str) -> Section:
    return self._sections[heading]
```

```python
# ✅ Good — the tolerant and the strict lookup are two names, and each keeps its word
def find_section(self, heading: str) -> Section | None:
    return self._sections.get(heading)


def require_section(self, heading: str) -> Section:
    return self._sections[heading]
```

## 5. `iter_` Is Lazy, `list_` and Plurals Are Materialized

`iter_<things>()` returns an `Iterator` and produces items on demand, like `re.finditer`, `Path.iterdir`, and
`ast.iter_child_nodes`. `list_<things>()` and a plural noun return a finished `tuple` or `list`, like
`re.findall` and `os.listdir`. A caller who iterates twice, takes `len()`, or holds the result past a change
to the source needs to know which one they have, and the annotation is read only by those who look.

## 6. `ensure_` Is Idempotent, Tolerance Is a Keyword

`ensure_<thing>()` creates the thing if absent and succeeds if present, so calling it twice equals calling it
once; it never means "assert". An effect with a strict and a tolerant form takes the strict form under the
plain name and the tolerance as a keyword, the way `Path.unlink(missing_ok=True)` and
`os.makedirs(exist_ok=True)` do, rather than as a second name (`set.remove`/`set.discard`) the reader must
already know.

## 7. A Guard Is `reject_<what it rejects>` and Returns `None`

A function that returns nothing and raises when its input is unacceptable is named for the case it rejects:
`reject_linked_layout`, `reject_invalid_namespace`. It is not `require_`, which is a lookup that returns what
it found ([§4](#4-the-name-says-what-absence-does)), and not `validate_`, which names a check that returns its
findings rather than raising the first one.

Naming the rejected case tells the reader what makes the call raise without opening the body; a name for the
accepted case (`require_real_layout`) leaves them to guess which of its many failures are refused.

## 8. `connect`/`disconnect` Is the Lifecycle Pair

A component that holds an external resource opens it with `connect()` and releases it with `disconnect()`.
Not `open`/`close`, not `start`/`stop`, not `connect`/`close`.

The standard library's pair is `close`, and choosing otherwise is deliberate. A mixed vocabulary is worse than
either consistent choice: a reader checks the source every time to learn which name a component uses, and a
generic teardown path that calls one of them silently skips the components that spell it the other way.
`disconnect` is visibly the inverse of `connect` in a way `close` is not.

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
raise. The context-manager protocol that wraps the pair is owned by
[pattern-resource-lifecycle](pattern-resource-lifecycle.md).

## Checklist

Before committing code, verify:

- [ ] Every `bool`-returning function reads as a question (`is_`/`has_`/`supports_`/`_exists`) and performs
      no mutation
- [ ] Every function that mutates opens with a verb and returns `None`; no mutator returns `self`, and no
      function takes an `inplace=` flag
- [ ] No `get_` prefix on an accessor that only returns stored state; those are properties or bare attributes
- [ ] Every `find_` returns `X | None`; every lookup without `| None` raises; tolerant twins end `_or_none`;
      no name starts with `try_`
- [ ] Every `iter_` returns an `Iterator`; every `list_` or plural name returns a `tuple` or `list`
- [ ] Every `ensure_` is idempotent create-if-absent; tolerant effects take a keyword such as `missing_ok=`
- [ ] Every function that returns `None` and raises on unacceptable input is `reject_<the rejected case>`,
      never `require_` or `validate_`
- [ ] A component holding an external resource spells its lifecycle `connect`/`disconnect`, and both are safe
      to call twice

## References

- [python-fn](python-fn.md) - Extends: Owns parameter kinds and defaults of the functions named here
- [python-fn-conv](python-fn-conv.md) - Related: Owns `as_`/`to_`, `from_`/`parse_`/`load_`, and `with_`
- [python-fn-unchecked](python-fn-unchecked.md) - Related: Owns the `_unchecked` constructor and its proof
- [python-naming](python-naming.md) - Related: Owns casing and the leading-underscore privacy boundary
- [pattern-resource-lifecycle](pattern-resource-lifecycle.md) - Related: The acquire/release protocol behind
  the `connect`/`disconnect` pair
- [principle-least-surprise](principle-least-surprise.md) - Foundation: Why a name that contradicts its cost
  or its effect is a defect

## External References

- [Rust API Guidelines: Naming](https://rust-lang.github.io/api-guidelines/naming.html)
- [Python Design FAQ: Why doesn't `list.sort()` return the sorted list?](https://docs.python.org/3/faq/design.html#why-doesn-t-list-sort-return-the-sorted-list)
- [SQLAlchemy: `Result.one_or_none`](https://docs.sqlalchemy.org/en/20/core/connections.html#sqlalchemy.engine.Result.one_or_none)
- [PDEP-8: In-place methods in pandas](https://pandas.pydata.org/pdeps/0008-inplace-methods-in-pandas.html)
