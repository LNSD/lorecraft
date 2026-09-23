---
name: "pattern-value-object"
description: "Value objects for identity, invariants, and units: a frozen one-field dataclass whose only validator is parse(). Load when a domain value is a bare str or int, when two same-typed parameters sit side by side, or when a docstring states a constraint the type could have stated"
type: "core"
scope: "global"
---

# Value Object (Wrapped Primitive)

## Rule

A domain value carried as a bare `str` or `int` makes every reader remember an invariant the code could have
remembered for them. When the value has an **identity**, an **invariant**, or a **unit**, declare it as a value
object — a small frozen class wrapping one field — so that a transposed argument is a visible type mismatch and
the constraint lives in one place.

**Do not reach for `typing.NewType`.** It is erased at runtime: `NewType('CorpusName', str)` produces a
callable that returns its argument unchanged, so nothing is validated, nothing is enforced, and two distinct
`NewType`s over `str` are the same object at runtime. It buys a distinction only when a static type checker
runs. **This repository runs none** — `just check` is `ruff check`, and ruff lints rather than type-checks;
there is no mypy and no pyright in the toolchain. A `NewType` here is a comment that costs an import.

The mechanism that actually holds at runtime:

```python
@dataclass(frozen=True, slots=True)     # exactly one field
@classmethod
def parse(cls, raw: str) -> 'Self': ... # the only validator
def __str__(self) -> str: ...           # as convenient as the str it replaces
```

plus the same `parse` in the loader that builds a record out of parsed frontmatter, so deserialization runs the
same check rather than trusting the file.

A value earns a value object when it does at least one of three jobs:

1. **Identity** — same-typed values that must never be swapped: a corpus name, a document name, the fully
   qualified document reference built from them, and the name of the format specification the document is
   checked against, all meeting in one signature.
2. **Invariant** — a constraint established once, at the edge, and never re-checked: a non-empty heading, a
   lowercase corpus name, a positive word budget.
3. **Unit** — a unit, base, or convention a bare primitive cannot state: line number versus section index,
   inclusive last line versus exclusive end, a budget in words versus one in characters.

Three signals a value object is missing, all visible in a diff:

- Two parameters of the same primitive type sit side by side (`def report(document: str, section: str) -> None`).
- A `- 1` or `+ 1` whose meaning lives in a comment rather than in a type.
- A docstring saying what the type should have said: *"must be lowercase"*, *"exclusive"*, *"in words"*.

**The one guarantee Python cannot give.** In a language with enforced privacy, a wrapper type's invariant
rests on a **private field**: construction outside the validating constructor is a compile error. Python has no
privacy — a leading
underscore is a convention, and `CorpusName('NOT VALID')` calls the generated `__init__` and succeeds. A reader
arriving from a language with real privacy will look for the private field; it is not there and cannot be. The
replacement guarantee is two-part and weaker by design:

- **Constructed at the boundary only.** Every value object is built by `parse` where the value enters the
  process — CLI argument, format specification load, parsed frontmatter, a path walked off disk — and passed
  onward thereafter. A value object constructed all over the domain is a value object whose invariant nobody
  can locate.
- **`frozen=True`, so nothing mutates past the check.** The invariant is verified once and cannot be
  invalidated afterwards, which is the half of that guarantee Python *can* give.

Two further rules this pattern absorbs:

- **A conversion is a named classmethod, not a second `__init__`.** `DocumentRef.from_parts(corpus, name)`
  states what it converts. An `__init__` that accepts several shapes and sniffs which one it got hides the
  conversion inside the constructor and makes the invariant untraceable.
- **Parsing lives in one place, named the same everywhere.** The validator is `parse` on every value object in
  the codebase. Not `from_str` on one and `validate` on the next: a reader looking for where a value is checked
  must be able to guess the name.

## Examples

1. **Two names that are not the same name**
   Filing a finding takes the corpus and the document it belongs to. Both are strings, they sit side by side,
   and transposing them produces a plausible-looking call that runs.

```python
# ❌ Bad — two bare strings in the same signature. `record_finding(document, corpus, finding)`
# runs happily, files the finding under a corpus that holds no such document, and the only
# symptom appears later as a report listing zero findings for a document a review raised four
# against.
def record_finding(corpus: str, document: str, finding: Finding) -> None:
    ...
```

```python
# ✅ Good — two types, so a transposition is visible at the call site and the constraint is
# checked once, where the value entered.
@dataclass(frozen=True, slots=True)
class CorpusName:
    """A corpus name: lowercase ASCII, hyphens and underscores."""

    value: str

    @classmethod
    def parse(cls, raw: str) -> 'CorpusName':
        """Validate and wrap a raw corpus name.

        Args:
            raw: The corpus name as it arrived from the CLI, a config file, or frontmatter.

        Returns:
            The validated corpus name.

        Raises:
            InvalidCorpusNameError: If the name is empty or not lowercase ASCII.
        """
        if not _CORPUS_RE.fullmatch(raw):
            raise InvalidCorpusNameError(f'corpus name must be lowercase ASCII: {raw!r}')
        return cls(raw)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class DocumentName:
    """The name of a document within a corpus: its filename without `.md`."""

    value: str

    @classmethod
    def parse(cls, raw: str) -> 'DocumentName':
        if not raw:
            raise InvalidDocumentNameError('document name must not be empty')
        return cls(raw)

    def __str__(self) -> str:
        return self.value


def record_finding(corpus: CorpusName, document: DocumentName, finding: Finding) -> None:
    ...
```

2. **A base written into the type, and enforced at the edge**
   Line spans are half-open everywhere a document is sliced into sections, but `int` cannot say so, and the one
   caller that read the bound as inclusive pulled the next heading into the section above it.

```python
# ❌ Bad — the convention lives in a docstring, and the `- 1` that reconciles the two readings
# is copied to three call sites. The site that dropped it counted every section's prose budget
# with the following heading attached, so the report blamed each over-budget section on its
# neighbour until someone re-counted by hand.
def section_lines(first: int, last: int) -> Iterator[str]:
    """Return lines `first` through `last`, inclusive."""
    ...


body = section_lines(section.start, section.end - 1)
```

```python
# ✅ Good — the convention is the type, and the single conversion between the two readings
# lives in one method. A missing conversion is now a missing call, not an absent `- 1`.
@dataclass(frozen=True, slots=True)
class LineNumber:
    """A 1-based line number. Distinct from a section index, which is also an int."""

    value: int

    @classmethod
    def parse(cls, raw: int) -> 'LineNumber':
        if raw < 1:
            raise InvalidLineNumberError(f'line number must be 1-based: {raw}')
        return cls(raw)

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class LineSpan:
    """A half-open span of lines: `first` included, `end` excluded."""

    first: LineNumber
    end: LineNumber

    def __post_init__(self) -> None:
        if self.end.value < self.first.value:
            raise InvalidLineSpanError(self.first, self.end)

    def last(self) -> LineNumber | None:
        """Return the inclusive last line, or None when the span is empty."""
        if self.first == self.end:
            return None
        return LineNumber(self.end.value - 1)


def section_lines(span: LineSpan) -> Iterator[str]:
    ...
```

A half-open span may be empty when `first == end`. An operation that asks for an element of the span makes that
case explicit rather than manufacturing a value outside the element type's invariant. Reversed bounds are
rejected when the span is constructed.

3. **The same check where the document is read**
   A document reference arrives in a document's own frontmatter. Wrapping it in the domain but letting the
   loader carry a bare `str` means the check runs everywhere except the one place untrusted input enters.

```python
# ❌ Bad — the loader copies parsed frontmatter straight into the record, so a name with a
# stray uppercase segment reaches the outline checker, is used to build the reference printed
# in every finding, and fails deep in the report writer with an error naming neither the
# frontmatter field nor the offending value.
@dataclass(frozen=True, slots=True)
class Frontmatter:
    name: str
    spec: str


def load_frontmatter(raw: dict[str, str]) -> Frontmatter:
    return Frontmatter(name=raw['name'], spec=raw['spec'])
```

```python
# ✅ Good — the loader runs the same `parse` the rest of the code runs, so an invalid name is
# rejected while the document is being read, with the offending value in the message, and
# everything downstream holds a checked value.
@dataclass(frozen=True, slots=True)
class Frontmatter:
    name: DocumentName
    spec: DocumentRef


def load_frontmatter(raw: dict[str, str]) -> Frontmatter:
    return Frontmatter(
        name=DocumentName.parse(raw['name']),
        spec=DocumentRef.parse(raw['spec']),
    )
```

4. **A conversion is a named classmethod, not a second `__init__`**
   A document reference can be built from a joined string or from its two parts. Handling both inside
   `__init__` makes the constructor a type switch and hides which path validated what.

```python
# ❌ Bad — one constructor, two meanings, decided by sniffing the arguments. A caller passing
# a corpus object where a joined reference was expected silently takes the other branch, and
# the resulting reference names a document nobody asked for.
class DocumentRef:
    def __init__(self, first: str | CorpusName, second: str | None = None) -> None:
        if second is None:
            self.corpus, self.name = first.split('/', 1)
        else:
            self.corpus, self.name = str(first), second
```

```python
# ✅ Good — one validator named `parse`, one conversion named for what it converts. Each has
# one meaning and one failure mode, and neither can be reached by accident.
@dataclass(frozen=True, slots=True)
class DocumentRef:
    """A fully qualified document reference: `<corpus>/<document>`."""

    corpus: CorpusName
    name: DocumentName

    @classmethod
    def parse(cls, raw: str) -> 'DocumentRef':
        """Parse a slashed reference such as `code/python-naming`.

        Raises:
            InvalidDocumentRefError: If the reference is not exactly two slashed segments.
        """
        try:
            corpus, name = raw.split('/', 1)
        except ValueError as exc:
            raise InvalidDocumentRefError(f'expected <corpus>/<document>, got {raw!r}') from exc
        return cls(CorpusName.parse(corpus), DocumentName.parse(name))

    @classmethod
    def from_parts(cls, corpus: CorpusName, name: DocumentName) -> 'DocumentRef':
        """Build a reference from two values that are already validated."""
        return cls(corpus, name)

    def __str__(self) -> str:
        return f'{self.corpus}/{self.name}'
```

## Why It Matters

**The type remembers, so the reader does not.** "The first argument is the corpus"; "this span is half-open";
"this string is a reference, not a bare name" — each is a fact a maintainer holds in their head at every call
site, and forgets exactly once. In a repository with no static type checker, the compensating mechanism has to
be a real runtime object, not an annotation.

**The failures this prevents are the quiet ones.** A transposed identifier files a well-formed finding against
the wrong document; a dropped `- 1` folds one heading into the section above it. Neither raises, neither fails a
test, and both read as correct code in review. A distinct type makes the first jump out of a diff and makes the
second a missing method call.

**An invariant checked at the edge stays checked.** A `CorpusName` that exists has been through `parse`, so
nothing downstream re-validates it, defends against it, or trusts a docstring — the check at the edge is
carried by the type rather than by discipline.

**Equality and hashing come free.** `frozen=True` generates `__eq__` and `__hash__` from the fields, so a value
object is a dict key and a set member with no extra code, and two references to the same document compare equal
without anyone writing a comparison. `slots=True` keeps the wrapper cheap and blocks stray attributes.

**`__str__` keeps it as convenient as the primitive.** `f'checking {document}'` and `str(document)` read exactly
as they did before the wrapper, so nobody reaches past the type for the inner field.

## Pragmatism Caveat

Wrap a value that has an invariant, a unit, or a confusable sibling. A value object with nothing to distinguish
and nothing to check is ceremony, and ceremony is what makes the next reader stop trusting the pattern:

- **No sibling, no invariant, no value object.** A finding's message, a log line, an author's free-form note in
  a document: there is nothing to swap them with and nothing to check. Leave them `str`.
- **A dataclass with named fields blunts the swap hazard** that positional parameters create. Two values that
  are genuinely the same kind playing different roles want one dataclass with named fields, not two wrappers
  differing only in name.
- **A value object is not a validator for external state.** "Does this document exist on disk?", "is this
  schema still the one its corpus declares?" depend on the world, not on the value. Those stay runtime checks
  in the domain.
- **Keep validation off hot paths.** `parse` runs on every construction: right once per document loaded, wrong
  per line inside a section scan. Wrap the document's identity, not each line of its prose.
- **If wrapping forces callers to unwrap immediately**, the boundary is in the wrong place. Move `parse` to the
  edge the value actually enters through, and give the type the method the caller was reaching for.

Deviating from this pattern is legitimate when one of the cases above applies and the reason is written down at
the spot. **An undocumented deviation is always wrong** — a bare `str` where a checked value was expected is
indistinguishable from an oversight, and the next reader will treat it as one.

## Checklist

- [ ] Every domain value with an invariant, a unit or base, or a confusable same-typed sibling is a value object
- [ ] `typing.NewType` is not used to make the distinction — nothing in this repository would enforce it
- [ ] The wrapper is `@dataclass(frozen=True, slots=True)` with exactly one meaningful field
- [ ] The validator is a classmethod named `parse`, and it is the only validator
- [ ] The value object is constructed at the boundary the value enters through, and nowhere else
- [ ] A conversion is a named classmethod (`from_parts`), never a second branch inside `__init__`
- [ ] Deserialization validates through the same `parse`, rather than storing the bare primitive
- [ ] `__str__` is defined, so interpolation and logging never reach for the inner field
- [ ] A composite range validates its bound ordering, and element access represents an empty range explicitly
- [ ] A conversion between two value objects (half-open to inclusive, parts to reference) exists in exactly one place
- [ ] No wrapper was added to a value with nothing to confuse it with and no invariant to carry

## References

- [principle-least-surprise](principle-least-surprise.md) - Foundation: A signature saying `str` twice surprises the caller who transposes them
- [pattern-registry](pattern-registry.md) - Related: Registry keys are exactly the kind of identity that earns a value object
- [pattern-resource-lifecycle](pattern-resource-lifecycle.md) - Related: A lifecycle is one state value, not several booleans

## External References

- [Parse, Don't Validate](https://lexi-lambda.github.io/blog/2019/11/05/parse-don-t-validate/)
- [Martin Fowler — Value Object](https://martinfowler.com/bliki/ValueObject.html)
- [Python docs — `dataclasses.dataclass`](https://docs.python.org/3/library/dataclasses.html#dataclasses.dataclass)
- [Python docs — `typing.NewType`](https://docs.python.org/3/library/typing.html#newtype)
