---
name: "python-typing"
description: "Types that make an invalid state unrepresentable instead of guarding it at runtime, and annotation spelling and honesty: builtin generics, `X | None`, `type` aliases, `Self`, justified `Any`, and static checking. Load when designing a record, union, or enum, adding a runtime guard for a state the types could exclude, or writing or reviewing a type annotation, alias, or alternative constructor"
type: "core"
scope: "global"
---

# Type Annotations

This document has two concerns. The first is types that make an invalid state unrepresentable, so a bad value
cannot be built instead of being checked for at runtime ([§1](#1-make-an-invalid-state-unrepresentable)). The
second is annotations that are spelled in one form and verified honestly against the code they describe.

Annotations are **required**, and `just typecheck` runs `ty` over the package. The checker is a floor, not a
ceiling: it catches a contradiction between an annotation and the body, and it cannot tell you that a
signature annotated `dict[str, Any]` promised almost nothing. So an annotation is still a **claim made to a
human reader**, and the reviewer still judges whether the claim is worth making. The sections after §1 follow
from that: spell annotations in the one modern form so they read uniformly, annotate every signature so the
claim is there to check, and never write an annotation you have not verified against the body. A green
checker on a vague annotation is not a pass.

`requires-python = ">=3.12"`, so there is no compatibility argument for the legacy spellings.

Naming of the annotated things is owned by [python-naming](python-naming.md). How a record's fields are
declared and defaulted is owned by [python-dataclasses](python-dataclasses.md). The prose that documents a
parameter is owned by [python-docstrings](python-docstrings.md). `Never`, and the branches an annotation
proves dead, are owned by [python-typing-unreachable](python-typing-unreachable.md).

## 1. Make an Invalid State Unrepresentable

Shape a type so that a state the program must never reach cannot be constructed, instead of constructing it
and guarding against it at runtime. A guard runs only on the paths its author thought of, and every reader of
the value has to trust that it ran. A type that cannot hold the bad value is checked by `ty` at every use, and
no reader needs a branch for it.

| Instead of | Write |
|------------|-------|
| One record whose fields only make sense in certain combinations, or a `kind` field that decides which other fields mean something | A union of records, one per case: `CorpusSpec \| NamespaceSpec` |
| A `kind` field whose type admits a case no value can be | One record per outcome that can occur: `ResolvedDirectory \| ResolvedFile` |
| A tuple read by its length | One record per shape: `CorpusSpecName \| NamespaceSpecName` |
| A plain value carrying a distinction no runtime check can see | A `NewType` ([pattern-newtype](pattern-newtype.md)): `ResolvedPath` |
| A non-empty guard on a collection whose first item is always there | A required field for that item ([python-dataclasses §4](python-dataclasses.md#4-no-optional-stands-in-for-set-later)) |
| A bare `str` naming one of several cases | An `Enum`, or a closed union when the cases carry different data |

```python
# ❌ Bad — `path` means something only when `kind` is 'file', so every reader re-asserts the pairing; one
# that forgot looked up `None` and reported every in-page link as broken
@dataclass(frozen=True, slots=True)
class LinkTarget:
    kind: str  # 'file' or 'anchor'
    path: RootRelativePath | None
    anchor: str | None


def target_exists(target: LinkTarget, files: frozenset[RootRelativePath], anchors: frozenset[str]) -> bool:
    if target.kind == 'file':
        assert target.path is not None
        return target.path in files
    assert target.anchor is not None
    return target.anchor in anchors
```

```python
# ✅ Good — each record holds only the fields its case has, so a file target without a path does not
# type-check and no reader asserts anything
@dataclass(frozen=True, slots=True)
class FileTarget:
    path: RootRelativePath


@dataclass(frozen=True, slots=True)
class AnchorTarget:
    anchor: str


type LinkTarget = FileTarget | AnchorTarget


def target_exists(target: LinkTarget, files: frozenset[RootRelativePath], anchors: frozenset[str]) -> bool:
    match target:
        case FileTarget(path=path):
            return path in files
        case AnchorTarget(anchor=anchor):
            return anchor in anchors
        case _:
            assert_never(target)
```

A `Literal` is already closed, and it is right where the value is its own meaning, such as a token a wire
model mirrors from a file format. Prefer an `Enum` where the cases are domain concepts, because each case is
then named once and renamed in one place rather than at every literal that spells it. Branching on a closed
union is owned by [python-typing-unreachable](python-typing-unreachable.md), and declaring each record by
[python-dataclasses](python-dataclasses.md).

A runtime check is still right at the edge. Input from outside the process has no type until it is parsed, so
it is validated once where it enters, and the parse returns the type that holds the result. Validating at the
edge is owned by [principle-validate-at-edge](principle-validate-at-edge.md), and the value object that
validates on construction by [pattern-value-object](pattern-value-object.md). What a check that the types
cannot replace raises is owned by [error-boundaries](error-boundaries.md).

## 2. Builtin Generics and `|` Unions, Never `typing.Dict` or `Optional`

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

`typing` is still imported for what the builtins do not provide: `Any`, `NewType`, `Self`, `TYPE_CHECKING`,
`ClassVar`, `Final`, `Callable`, `Iterator`.

**Enforcement:** ruff `UP` (UP006, UP007, UP035, UP045) — not currently enabled; see the checklist.

## 3. Every Public Signature Is Annotated

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

## 4. `Any` Is a Last Resort and Names Its Reason

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

    Values are `Any` because the YAML parser decodes each field to its own Python
    type and the schema that narrows them is corpus-specific.
    """
    ...
```

```python
# 🔶 Acceptable — a parser handle with no public type to name
self._parser: Any = yaml_backend.make_parser(stream)  # backend exposes no parser type
```

## 5. `TYPE_CHECKING` Guards Cycle-Only Imports and the Annotation Is a String

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
    from lorecraft.registry import SpecRegistry


@dataclass
class CorpusCheck:
    registry: SpecRegistry
```

```python
# ✅ Good — guarded import, quoted annotation; the name is never looked up at runtime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lorecraft.registry import SpecRegistry


@dataclass
class CorpusCheck:
    registry: 'SpecRegistry'
```

The guard is for cycles, not for import cost. An import with no cycle is written normally — hiding it behind
the guard means the module can no longer use the name in an `isinstance` check or a default, and the next
person to need it there writes a second, unguarded import of the same thing.

## 6. Declare Structural Aliases With `type`

Use the Python 3.12 `type` statement to name a reusable type expression. A plain assignment looks like a
runtime value, while `type` tells the reader and checker that the name is an alias. `TypeAlias` is the older
spelling and is unnecessary for this project's minimum Python version.

```python
# ❌ Bad — the assignment does not make the alias declaration explicit
SchemaKey = tuple[str, str]
```

```python
# ✅ Good — the declaration marks the name as a type alias
type SchemaKey = tuple[str, str]
```

`type` creates a `TypeAliasType`, whose value is evaluated lazily. Code that needs an actual runtime type
expression uses that expression directly rather than assuming the alias itself is one.

## 7. Return `Self` From an Alternative Constructor

Annotate a classmethod that constructs `cls` with `Self`. A hard-coded class return type hides the fact that
the same method called on a subclass returns that subclass. Use the concrete class name when the method
deliberately constructs that class regardless of which subclass calls it.

```python
# ❌ Bad — a subclass call is annotated as returning only the base class
class CorpusLabel:
    @classmethod
    def parse(cls, raw: str) -> 'CorpusLabel':
        return cls(raw)
```

```python
# ✅ Good — the return type follows the class on which parse was called
class CorpusLabel:
    @classmethod
    def parse(cls, raw: str) -> Self:
        return cls(raw)
```

## 8. Review the Claims That `ty` Cannot Prove

`just typecheck` runs `ty` over the package. A clean check catches many mismatches, but it cannot prove that
an annotation expresses the intended contract: `Any` can hide a mismatch, and `str` can admit values whose
domain meaning has not been checked. A reviewer checks the claim against the body and its callers even when
`ty` passes.

A reviewer reads every annotation in a diff against the body that backs it, and asks three questions:

| Question | The defect it catches |
|----------|-----------------------|
| Can this function return `None` on any path? | A branch hidden by `Any` or an ignored diagnostic can leave `-> FormatSpec` on a body that returns `None` |
| Does the declared parameter type express what callers may pass? | `str` can admit arbitrary text where the caller must supply a validated document name |
| Did the return type survive the last edit? | A widened `Any` can make an outdated return annotation pass the checker |

```python
# ❌ Bad — Any hides the absent result from the checker and the return annotation
def spec_for(self, corpus: str) -> FormatSpec:
    value: Any = self._specs.get(corpus)
    return value
```

```python
# ✅ Good — the source's optional result remains visible to the caller and checker
def spec_for(self, corpus: str) -> FormatSpec | None:
    return self._specs.get(corpus)
```

An annotation is not runtime validation: `ty` checks statically known calls, and a bad value from outside the
process is rejected at the edge ([§1](#1-make-an-invalid-state-unrepresentable)).

## Checklist

Before committing code, verify:

- [ ] No new record carries fields that only make sense in combination, a `kind` that decides which other
      fields mean something or admits a case no value can be, a tuple read by its length, or a bare `str`
      naming one of several cases; a `Literal` appears only where the value is its own meaning; and no guard
      checks for a state a union of records, a record per shape, a `NewType`, a required field, or an `Enum`
      could exclude
- [ ] No `typing.Dict`, `List`, `Tuple`, `Set`, `Type`, `Optional`, or `Union` in the diff; builtin generics
      and `|` are used instead
- [ ] Every public function, method, and `__init__` has annotated parameters and an explicit return type,
      `-> None` included
- [ ] Each `Any` is either an opaque third-party value, a `**kwargs` passthrough, or unvalidated input, and
      the reason is stated
- [ ] Every import under `if TYPE_CHECKING:` exists to break a cycle, and each annotation using it is quoted
- [ ] A new structural alias uses `type`, and code that needs a runtime type expression does not use the alias
      object as that expression
- [ ] An alternative constructor that constructs `cls` returns `Self`, preserving the subclass result
- [ ] Every changed signature was read against its body: no path returns `None` under a non-optional return
      type, no `Any` hides a mismatch, and no annotation was left behind by the edit; `just typecheck` passes

## References

- [python-dataclasses](python-dataclasses.md) - Related: Field declaration, defaults, the required field that
  replaces a set-later `None`, and `__post_init__` validation on annotated records
- [python-naming](python-naming.md) - Related: What the annotated attributes and classes are called
- [python-fn-names](python-fn-names.md) - Related: The return type a function's name promises
- [python-docstrings](python-docstrings.md) - Related: The `Args:`/`Returns:` prose that accompanies a
  signature
- [python-constants](python-constants.md) - Related: When a module-level name is annotated `Final[...]`
- [python-modules](python-modules.md) - Related: Import placement and ordering, including the
  `TYPE_CHECKING` block
- [python-typing-unreachable](python-typing-unreachable.md) - Related: Owns `Never`, the `match` closed by
  `assert_never` over a closed union, and the paths `ty` cannot prove dead
- [pattern-newtype](pattern-newtype.md) - Related: Owns the static distinction for a value no runtime check
  can tell apart
- [pattern-value-object](pattern-value-object.md) - Related: Owns the value object that validates its
  invariant on construction
- [error-boundaries](error-boundaries.md) - Related: Owns whether a failed check raises a built-in or an
  `Error` variant
- [principle-validate-at-edge](principle-validate-at-edge.md) - Foundation: Input from outside the process is
  validated once where it enters, then trusted as a type

## External References

- [PEP 604 - Allow writing union types as X | Y](https://peps.python.org/pep-0604/)
- [PEP 585 - Type Hinting Generics In Standard Collections](https://peps.python.org/pep-0585/)
- [PEP 695 - Type Parameter Syntax](https://peps.python.org/pep-0695/)
- [PEP 673 - Self Type](https://peps.python.org/pep-0673/)
- [typing.assert_never - Python Standard Library](https://docs.python.org/3/library/typing.html#typing.assert_never)
