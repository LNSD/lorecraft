---
name: "pattern-value-object"
description: "Runtime-validated value objects with documented invariants and a parse() boundary. Load when a domain value needs parsing, a runtime invariant, or behavior of its own"
type: "core"
scope: "global"
---

# Value Object (Wrapped Primitive)

## Rule

A domain value carried as a bare `str` or `int` makes every reader remember an invariant the code could have
remembered for them. When a value needs **runtime validation**, a **unit**, or behavior of its own, declare it
as a value object — a small frozen class wrapping one field — so that the constraint lives in one place. For a
pure static distinction between values with no runtime invariant, use [`typing.NewType`](pattern-newtype.md).

`NewType` provides only a static distinction; it does not validate or wrap its input at runtime.

The mechanism that actually holds at runtime:

```python
@dataclass(frozen=True, slots=True)     # exactly one field
@classmethod
def parse(cls, raw: str) -> 'Self': ... # named input boundary
def __post_init__(self) -> None: ...    # guard direct construction when needed
def __str__(self) -> str: ...           # as convenient as the str it replaces
```

plus the same `parse` in the loader that builds a record out of parsed frontmatter, so deserialization runs the
same check rather than trusting the file.

State the complete value format in the class docstring, beside the field whose value carries it. Name accepted
characters, excluded forms, bounds, case handling and normalization where they apply. The class docstring tells
a caller what can be constructed before they have an invalid input.

A failed parse raises a value-specific error declared beside the value object, under the package's domain error
hierarchy. The error owns the rejected value and useful failure context, such as the invalid character and its
position, and builds the message. `parse` or a direct-construction guard selects the failure and raises the
error without composing its text. [python-exceptions](python-exceptions.md) owns the hierarchy and
structured-context rules.

A value earns a value object when it does at least one of three jobs:

1. **Identity with a runtime contract** — same-typed values that must never be swapped and also need parsing or
   behavior: a corpus name validated against its allowed spelling, or a fully qualified document reference
   with separately checked parts.
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
enforced privacy. A leading underscore is a convention, and a caller can deliberately bypass construction. The
ordinary constructor can still uphold the invariant: when direct construction must be safe, check the field in
`__post_init__` and let `parse` delegate to `cls(raw)`. The practical guarantee has two parts:

- **Constructed at the boundary only.** Call `parse` where the value enters the process — CLI argument, format
  specification load, parsed frontmatter, a path walked off disk — and pass the object onward thereafter. A
  value object constructed all over the domain is a value object whose invariant nobody can locate. The
  `__post_init__` guard prevents an ordinary direct constructor call from bypassing validation.
- **`frozen=True`, so nothing mutates past the check.** The invariant is verified once and cannot be
  invalidated afterwards, which is the half of that guarantee Python *can* give.

Two further rules this pattern absorbs:

- **A conversion is a named classmethod, not a second `__init__`.** `DocumentRef.from_parts(corpus, name)`
  states what it converts. An `__init__` that accepts several shapes and sniffs which one it got hides the
  conversion inside the constructor and makes the invariant untraceable.
- **Parsing has one public name.** The input boundary is `parse` on every value object in the codebase. Not
  `from_str` on one and `validate` on the next: a reader looking for where a value is checked must be able to
  guess the name. If `__post_init__` enforces direct construction, `parse` delegates to it rather than
  duplicating the check.

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
class CorpusNameError(Error):
    """Base class for corpus-name validation failures."""


class EmptyCorpusNameError(CorpusNameError):
    """A corpus name is empty."""

    def __init__(self) -> None:
        self.name = ''
        super().__init__('corpus name cannot be empty')


class InvalidCorpusNameCharacterError(CorpusNameError):
    """A corpus name contains a character outside its required format.

    Attributes:
        name: The rejected corpus name.
        position: Zero-based position of the invalid character.
        character: The invalid character.
    """

    def __init__(self, name: str, position: int) -> None:
        self.name = name
        self.position = position
        self.character = name[position]
        super().__init__(f'invalid character {self.character!r} in corpus name {name!r}')


@dataclass(frozen=True, slots=True)
class CorpusName:
    """A validated corpus name.

    A valid name matches ``[a-z_][a-z0-9_]*``:

    - Is not empty.
    - Starts with a lowercase ASCII letter or underscore.
    - Continues with only lowercase ASCII letters, digits or underscores.

    Parsing preserves the spelling.

    Attributes:
        value: The validated name, exactly as supplied.
    """

    value: str

    @classmethod
    def parse(cls, raw: str) -> 'CorpusName':
        """Validate and wrap a raw corpus name.

        Args:
            raw: The corpus name as it arrived from the CLI, a config file, or frontmatter.

        Returns:
            The validated corpus name.

        Raises:
            CorpusNameError: If the name is not lowercase snake case.
        """
        if not raw:
            raise EmptyCorpusNameError()
        if raw[0] not in ascii_lowercase + '_':
            raise InvalidCorpusNameCharacterError(raw, 0)
        for position, character in enumerate(raw[1:], start=1):
            if character not in ascii_lowercase + digits + '_':
                raise InvalidCorpusNameCharacterError(raw, position)
        return cls(raw)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class DocumentName:
    """A document's non-empty filename stem, without `.md`."""

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
site, and forgets exactly once. When the fact needs runtime validation, the value object carries the check with
the value instead of relying on a static distinction.

**The failures this prevents are the quiet ones.** A transposed identifier files a well-formed finding against
the wrong document; a dropped `- 1` folds one heading into the section above it. Neither raises, neither fails a
test, and both read as correct code in review. A distinct type makes the first jump out of a diff and makes the
second a missing method call.

**An invariant checked at the edge stays checked.** A `CorpusName` built through `parse` has been checked, so
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
- **Keep validation off hot paths.** Validation runs on every construction: right once per document loaded, wrong
  per line inside a section scan. Wrap the document's identity, not each line of its prose.
- **If wrapping forces callers to unwrap immediately**, the boundary is in the wrong place. Move `parse` to the
  edge the value actually enters through, and give the type the method the caller was reaching for.

Deviating from this pattern is legitimate when one of the cases above applies and the reason is written down at
the spot. **An undocumented deviation is always wrong** — a bare `str` where a checked value was expected is
indistinguishable from an oversight, and the next reader will treat it as one.

## Checklist

- [ ] Every domain value with a runtime invariant, a unit or base, or behavior of its own is a value object
- [ ] A pure static distinction without a runtime invariant uses `typing.NewType` ([pattern-newtype](pattern-newtype.md))
- [ ] The wrapper is `@dataclass(frozen=True, slots=True)` with exactly one meaningful field
- [ ] The class docstring states the complete value format and whether parsing normalizes the input
- [ ] The input boundary is a classmethod named `parse`; a direct-construction guard in `__post_init__` shares its check
- [ ] Rejection raises a value-specific domain error declared beside the value object; the error owns the
      rejected value, useful context and message
- [ ] The value object is constructed at the boundary the value enters through, and nowhere else
- [ ] A conversion is a named classmethod (`from_parts`), never a second branch inside `__init__`
- [ ] Deserialization validates through the same `parse`, rather than storing the bare primitive
- [ ] `__str__` is defined, so interpolation and logging never reach for the inner field
- [ ] A composite range validates its bound ordering, and element access represents an empty range explicitly
- [ ] A conversion between two value objects (half-open to inclusive, parts to reference) exists in exactly one place
- [ ] No wrapper was added to a value with nothing to confuse it with and no invariant to carry

## References

- [principle-least-surprise](principle-least-surprise.md) - Foundation: A signature saying `str` twice surprises the caller who transposes them
- [pattern-newtype](pattern-newtype.md) - Related: Static-only distinctions for values without runtime invariants
- [python-exceptions](python-exceptions.md) - Related: Domain error hierarchy and structured failure context
- [pattern-registry](pattern-registry.md) - Related: Registry keys are exactly the kind of identity that earns a value object
- [pattern-resource-lifecycle](pattern-resource-lifecycle.md) - Related: A lifecycle is one state value, not several booleans

## External References

- [Parse, Don't Validate](https://lexi-lambda.github.io/blog/2019/11/05/parse-don-t-validate/)
- [Martin Fowler — Value Object](https://martinfowler.com/bliki/ValueObject.html)
- [Python docs — `dataclasses.dataclass`](https://docs.python.org/3/library/dataclasses.html#dataclasses.dataclass)
- [Python docs — `typing.NewType`](https://docs.python.org/3/library/typing.html#newtype)
