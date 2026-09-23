---
name: "python-typing"
description: "Annotation spelling and honesty: builtin generics, `X | None`, annotated public signatures, justified `Any`, `TYPE_CHECKING` cycle imports, and the checker as a floor rather than a ceiling. Load when writing or reviewing a type annotation, adding a generic base, or declaring a protocol"
type: "core"
scope: "global"
---

# Type Annotations

Annotations are **required**, and `just typecheck` runs `ty` over the package. The checker is a floor, not a
ceiling: it catches a contradiction between an annotation and the body, and it cannot tell you that a
signature annotated `dict[str, Any]` promised almost nothing. So an annotation is still a **claim made to a
human reader**, and the reviewer still judges whether the claim is worth making. Everything below follows
from that: spell annotations in the one modern form so they read uniformly, annotate every signature so the
claim is there to check, and never write an annotation you have not verified against the body. A green
checker on a vague annotation is not a pass.

`requires-python = ">=3.12"`, so there is no compatibility argument for the legacy spellings.

Naming of the annotated things is owned by [python-naming](python-naming.md). How a record's fields are
declared and defaulted is owned by [python-dataclasses](python-dataclasses.md). The prose that documents a
parameter is owned by [python-docstrings](python-docstrings.md).

## 1. Builtin Generics and `|` Unions, Never `typing.Dict` or `Optional`

Write `dict[str, Any]`, `list[Finding]`, `tuple[int, int]`, and `X | None`. The `typing` aliases
(`Dict`, `List`, `Tuple`, `Set`, `Type`) and `Optional[X]` / `Union[X, Y]` do not appear in new code.

Two spellings for one type means a reader comparing two signatures has to normalize them before they can see
whether they agree, and a module that mixes both makes every `from typing import` line a question about which
era the file is from.

```python
# ❌ Bad — three imports to say what the builtins already say, and `Optional` hides that
# the caller must handle an absent override map on every read of this signature
from typing import Dict, List, Optional


def load_documents(corpus: str, spans: List[tuple], overrides: Optional[Dict[str, str]] = None) -> List[str]:
    ...
```

```python
# ✅ Good — one spelling, and `| None` puts the absent case in the reader's eye
def load_documents(
    corpus: str,
    spans: list[tuple[int, int]],
    overrides: dict[str, str] | None = None,
) -> list[str]:
    ...
```

`typing` is still imported for what the builtins do not provide: `Any`, `TypeVar`, `Generic`, `Protocol`,
`TYPE_CHECKING`, `ClassVar`, `Callable`, `Iterator`.

**Enforcement:** ruff `UP` (UP006, UP007, UP035, UP045) — not currently enabled; see the checklist.

## 2. Every Public Signature Is Annotated

Every parameter and the return type of every public function, method, and constructor carries an annotation,
including `-> None`. A private helper follows the same rule whenever its types are not obvious from two lines
of body.

An unannotated `-> None` and a forgotten return annotation look identical in a diff. Writing `-> None`
explicitly is what turns "this function returns nothing" into a statement rather than an omission.

```python
# ❌ Bad — does it return the finding count, the report, or nothing? The caller finds out
# by running it, and a later change to return a count breaks nobody's expectations
# because there were none
def flush_findings(self, corpus_name):
    self._report.write_all()
```

```python
# ✅ Good — the signature answers both questions before the body is read
def flush_findings(self, corpus_name: str) -> None:
    """Flush buffered findings for a corpus.

    Args:
        corpus_name: Corpus whose finding buffer is drained into the report.
    """
    self._report.write_all()
```

`self` and `cls` are never annotated. `*args` and `**kwargs` are annotated with the type of a single value
(`**kwargs: Any`), not the container.

## 3. `Any` Is a Last Resort and Names Its Reason

`Any` switches off the claim. Use it only where the value genuinely has no type the reader could act on — a
third-party parser's opaque handle, a `**kwargs` passthrough, a frontmatter mapping not yet validated against
its schema — and say which in a comment or in the docstring.

An `Any` written because the real type was inconvenient to look up is indistinguishable from one written
because no real type exists, so the next reader cannot tell whether narrowing it is safe.

```python
# ❌ Bad — a frontmatter block does have a known shape; `Any` here means the next reader
# cannot tell whether entries are mappings, strings, or parsed nodes without running
# the parser
def frontmatter_blocks(self, corpus: str) -> list[Any]:
    ...
```

```python
# ✅ Good — the shape is stated, and the one genuinely opaque value says why
def frontmatter_blocks(self, corpus: str) -> list[dict[str, Any]]:
    """Return each document's frontmatter as a field-name mapping.

    Values are ``Any`` because the YAML parser decodes each field to its own Python
    type and the schema that narrows them is corpus-specific.
    """
    ...
```

```python
# 🔶 Acceptable — a parser handle with no public type to name
self._parser: Any = yaml_backend.make_parser(stream)  # backend exposes no parser type
```

## 4. `TYPE_CHECKING` Guards Cycle-Only Imports and the Annotation Is a String

An import needed **only** for an annotation, whose eager form would create an import cycle, goes under
`if TYPE_CHECKING:`, and every annotation that uses it is quoted.

The guard removes the import at runtime, so an unquoted annotation referring to it raises `NameError` the
moment anything evaluates annotations — a dataclass field, `typing.get_type_hints`, a runtime validator. The
quotes are not stylistic; they are what makes the guard safe.

```python
# ❌ Bad — the name does not exist at runtime, so constructing this dataclass raises
# NameError on the field whose type it resolves
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lorewright.registry import SpecRegistry


@dataclass
class CorpusCheck:
    registry: SpecRegistry
```

```python
# ✅ Good — guarded import, quoted annotation; the name is never looked up at runtime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lorewright.registry import SpecRegistry


@dataclass
class CorpusCheck:
    registry: 'SpecRegistry'
```

The guard is for cycles, not for import cost. An import with no cycle is written normally — hiding it behind
the guard means the module can no longer use the name in an `isinstance` check or a default, and the next
person to need it there writes a second, unguarded import of the same thing.

## 5. `TypeVar` and `Generic` for a Parameterized Base, `Protocol` for a Seam You Do Not Own

Use `TypeVar` + `Generic[T]` when a base class is genuinely parameterized by a type its subclasses pick — a
checker base parameterized by its configuration record is the archetype. Use `Protocol` when you need to
describe the shape of something you did not define and cannot make inherit from you: a third-party parser, a
callback the caller supplies, a sink object passed in from outside.

Reaching for `Protocol` where a real base class exists loses the shared implementation; reaching for
inheritance across a boundary you do not own is not available at all.

```python
# ❌ Bad — the config type is erased, so every subclass re-states in a docstring what
# the signature could have carried, and a subclass handed the wrong config record
# fails somewhere inside `run` instead of at the call
class Checker:
    def __init__(self, config: Any) -> None:
        self.config = config
```

```python
# ✅ Good — the parameter travels with the class, so the subclass's config type is
# visible at its declaration
TConfig = TypeVar('TConfig')


class Checker(Generic[TConfig]):
    def __init__(self, config: TConfig) -> None:
        self.config = config


class OutlineChecker(Checker[OutlineCheckConfig]):
    ...
```

```python
# ✅ Good — a Protocol for a seam the caller fills; nothing here can be made to inherit
class FindingSink(Protocol):
    def report(self, finding: Finding) -> None: ...
```

A `Protocol` used only in one annotation, with one implementation, in one module, is a base class written the
long way. Delete it and annotate the concrete type.

## 6. Nothing Checks These Annotations, So a Reviewer Must

There is no `mypy` or `pyright` run in this repository. An annotation is therefore unverified prose that looks
like a guarantee, and a wrong one is **worse than none**: a missing annotation prompts the reader to check the
body, while a lying one persuades them not to.

A reviewer reads every annotation in a diff against the body that backs it, and asks three questions:

| Question | The defect it catches |
|----------|-----------------------|
| Can this function return `None` on any path? | `-> FormatSpec` on a body with a bare `return` or an early `return None` |
| Does every declared parameter type match what callers actually pass? | `document: str` on a method that is also called with a `RuleDocumentRef` |
| Did the return type survive the last edit? | A function that grew a `raise`/`return` pair and kept the old annotation |

```python
# ❌ Bad — annotated as total, but the early exit returns None. Every caller writes
# `spec.schema` and the ones that hit the unspecified-corpus path get an
# AttributeError at a line the annotation said was safe
def spec_for(self, corpus: str) -> FormatSpec:
    if corpus not in self._specs:
        return None
    return self._specs[corpus]
```

```python
# ✅ Good — the annotation matches every path, so the caller is told to handle absence
def spec_for(self, corpus: str) -> FormatSpec | None:
    if corpus not in self._specs:
        return None
    return self._specs[corpus]
```

The corollary is that an annotation is not a validation. A function that must reject a bad value validates it
in the body and raises; the annotation documents the intent, and nothing enforces it at the call. Where the
value crosses a boundary, that check is owed.

## Checklist

Before committing code, verify:

- [ ] No `typing.Dict`, `List`, `Tuple`, `Set`, `Type`, `Optional`, or `Union` in the diff; builtin generics
      and `|` are used instead
- [ ] Every public function, method, and `__init__` has annotated parameters and an explicit return type,
      `-> None` included
- [ ] Each `Any` is either an opaque third-party value, a `**kwargs` passthrough, or unvalidated input, and
      the reason is stated
- [ ] Every import under `if TYPE_CHECKING:` exists to break a cycle, and each annotation using it is quoted
- [ ] A parameterized base uses `TypeVar`/`Generic`; `Protocol` appears only for a type this project does not
      define
- [ ] Every changed signature was read against its body: no path returns `None` under a non-optional return
      type, and no annotation was left behind by the edit

## References

- [python-dataclasses](python-dataclasses.md) - Related: Field declaration, defaults, and `__post_init__`
  validation on annotated records
- [python-naming](python-naming.md) - Related: What the annotated functions and attributes are called
- [python-docstrings](python-docstrings.md) - Related: The `Args:`/`Returns:` prose that accompanies a
  signature
- [python-modules](python-modules.md) - Related: Import placement and ordering, including the
  `TYPE_CHECKING` block

## External References

- [PEP 604 - Allow writing union types as X | Y](https://peps.python.org/pep-0604/)
- [PEP 585 - Type Hinting Generics In Standard Collections](https://peps.python.org/pep-0585/)
- [PEP 544 - Protocols: Structural subtyping](https://peps.python.org/pep-0544/)
