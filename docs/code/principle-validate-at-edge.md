---
name: "principle-validate-at-edge"
description: "Validate at the Edge (hard shell, soft core) — parse untrusted input once at the boundary. Load when writing a command handler, loading a format spec or schema, decoding frontmatter, or reading any value from outside the process"
type: "principle"
scope: "global"
---

# Validate at the Edge (Hard Shell, Soft Core)

## Rule

Every value that enters from outside — a CLI argument, an environment variable, a JSON format specification,
a document's YAML frontmatter, a `SKILL.md`, a path walked off disk — arrives untrusted and typed wider than
reality. Parse it **once**, at the boundary, into a type the rest of the code can trust. Past that point, no
function re-checks. The boundary is the hard shell; the domain is the soft core. Concretely:

- An invariant is established in the value's `parse` classmethod, or in a `__post_init__` guard that `parse`
  delegates to — not in a standalone helper and not in a command body. That is the one place the invariant
  lives, and every entry point calls it.
- A command handler's job is to turn its arguments into domain types and hand them on. Domain functions take
  the parsed types, never the raw `str`.
- Untrusted input is annotated as what it is until it is parsed: `object`, or `Mapping[str, object]` for
  decoded YAML and JSON. A `TypedDict` or an `Any` that asserts a shape nobody checked is a trusted type on
  untrusted data.
- Malformed input degrades into a typed error at the edge — a rejected argument, a finding for that one
  document, a spec that fails to load — never a `KeyError` or an `AttributeError` three calls down.
- Unit and convention conversions happen once, at the boundary: `str` to `Path`, 1-based line number to
  0-based index, inclusive last line to exclusive end.

## Examples

1. **Parse into domain types at the boundary; the domain trusts them**
   A command receives strings. Everything past it receives meaning.

```python
# ❌ Bad — the domain function takes a raw string and validates it itself. Every other
# caller must remember to do the same, and the watch loop, which read the corpus off a
# path, did not: `Code` and `code` became two corpora and the first was never governed.
def check_corpus(corpus: str) -> list[Finding]:
    if not corpus:
        raise ValueError('corpus is empty')
    if corpus != corpus.lower():
        raise ValueError(f'corpus must be lowercase: {corpus!r}')
    ...  # the check, finally
```

```python
# ✅ Good — the invariant lives in the type; the command parses; the domain trusts.
# Every path into the domain goes through the same type, the watch loop included.
@dataclass(frozen=True, slots=True)
class CorpusName:
    """A corpus name: lowercase ASCII words joined by single hyphens, e.g. ``code-python``."""

    value: str

    def __post_init__(self) -> None:
        if re.fullmatch(r'[a-z]+(-[a-z]+)*', self.value) is None:
            raise InvalidCorpusNameError(self.value)

    @classmethod
    def parse(cls, raw: str) -> Self:
        return cls(raw)


# Boundary
def check_command(corpus: str) -> None:
    try:
        name = CorpusName.parse(corpus)
    except InvalidCorpusNameError as exc:
        raise typer.BadParameter(str(exc)) from exc
    report(check_corpus(name))


# Domain — no defensive checks; the type carries the proof
def check_corpus(corpus: CorpusName) -> list[Finding]: ...
```

2. **Cross-field constraints belong to a composite type**
   A relationship between two fields is an invariant of the pair, so the pair is the type.

```python
# ❌ Bad — the ordering check sits in the one function that happened to need it, and the
# inclusive/exclusive convention is re-decided at every call site.
def excerpt(lines: Sequence[str], first: int, last: int) -> list[str]:
    if first > last:
        raise ValueError(f'inverted span: {first}..{last}')
    # is `last` inclusive here? the budget report two modules up assumed it was not
    return list(lines[first - 1 : last])
```

```python
# ✅ Good — the pair is a type, the ordering is its invariant, and the convention is
# stated once and carried in the field names.
@dataclass(frozen=True, slots=True)
class LineSpan:
    """A half-open span of 1-based line numbers: ``first`` included, ``end`` excluded."""

    first: int
    end: int

    def __post_init__(self) -> None:
        if not 1 <= self.first < self.end:
            raise EmptyLineSpanError(self.first, self.end)


def excerpt(lines: Sequence[str], span: LineSpan) -> list[str]:
    return list(lines[span.first - 1 : span.end - 1])
```

3. **A specification is decoded into validated types, once**
   A spec value checked wherever it is consumed is a spec value that is eventually consumed somewhere new.

```python
# ❌ Bad — the decoded JSON is trusted, and every consumer re-checks the parts it uses.
# The section check added last did not, and a budget of 0 flagged every section of every
# document with a finding that blamed the documents, not the spec.
@dataclass(frozen=True, slots=True)
class BudgetSpec:
    default: int
    sections: dict[str, int]


def is_over_budget(spec: BudgetSpec, section: str, words: int) -> bool:
    budget = spec.sections.get(section, spec.default)
    if budget <= 0:
        raise ValueError(f'budget must be positive: {budget}')
    return words > budget
```

```python
# ✅ Good — loading is the boundary. An invalid spec fails at load, naming the file and the
# reason, before a single document is read.
@dataclass(frozen=True, slots=True)
class WordBudget:
    """A prose budget in words: a positive integer."""

    words: int

    def __post_init__(self) -> None:
        if self.words <= 0:
            raise InvalidWordBudgetError(self.words)


@dataclass(frozen=True, slots=True)
class BudgetSpec:
    default: WordBudget
    sections: Mapping[str, WordBudget]


def load_budget_spec(path: Path) -> BudgetSpec:
    raw = json.loads(path.read_text(encoding='utf-8'))
    try:
        return BudgetSpec(
            default=WordBudget(raw['default']),
            sections={name: WordBudget(words) for name, words in raw['sections'].items()},
        )
    except (KeyError, TypeError, AttributeError, InvalidWordBudgetError) as exc:
        raise SpecLoadError(path, exc) from exc


def is_over_budget(spec: BudgetSpec, section: str, words: int) -> bool:
    return words > spec.sections.get(section, spec.default).words
```

4. **A malformed document degrades; it does not take the run down**
   A document is user-authored. It will eventually hold something its specification does not describe.

```python
# ❌ Bad — the parsed YAML is trusted to have the shape the schema promises. One document
# with `name:` left blank decoded to None, `.removesuffix` raised AttributeError, and the
# run died with a traceback instead of reporting that one document.
def document_name(frontmatter: dict[str, Any]) -> str:
    return frontmatter['name'].removesuffix('.md')
```

```python
# ✅ Good — decoding is fallible at the edge, and the error carries what is needed to act on
# it: which document, which field, what was there. The run turns it into a finding and
# moves on to the next document.
def document_name(path: Path, frontmatter: Mapping[str, object]) -> DocumentName:
    raw = frontmatter.get('name')
    if not isinstance(raw, str):
        raise FrontmatterFieldError(path, field='name', expected='a string', found=raw)
    return DocumentName.parse(raw)
```

## Why It Matters

This toolkit reads user-authored documents, hand-written JSON specifications and command-line arguments, any
of which can hold a value the types do not describe: a `null` where a string was promised, a budget of zero, a
span whose end precedes its start. Trusted where they land, the failure surfaces somewhere else entirely — a
traceback from a checker caused by a spec loaded seconds earlier, with nothing in the output tying the two
together.

A single narrow point also localizes the fix. When a specification gains a field, the one decode site is what
changes, and a malformed document is one finding rather than a dead run. Because the invariant lives in the
type, every entry point that reaches the same domain — the command, the watch loop, a test building a value by
hand — enforces it identically, for free. Scattered per-layer checks buy the opposite: three partial
contracts, and the union of them is nobody's job.

## Pragmatism Caveat

The signal for where a check belongs is what it depends on:

- **Depends only on the incoming value → the edge**: shape, required fields, formats, ranges, and cross-field
  constraints within one document or spec.
- **Depends on external state → the domain**: "does a spec govern this corpus?", "does the linked document
  exist?", "is this skill name already taken?". These need the rest of the workspace, and the edge does not
  have it.

Do not push state-dependent checks into the boundary, and do not let shape checks leak past it. Do not
re-validate in the soft core: a function taking a parsed type does not check its fields again. When a
re-check is deliberate, say why in a comment at that spot; an undocumented re-validation is always wrong — dead
code that hides where the real contract lives.

## Checklist

Before committing code, verify:

- [ ] Every invariant is established in a `parse` classmethod or `__post_init__`, not in a command body or a
      standalone helper
- [ ] Command handlers parse their arguments into domain types; domain functions never take the raw input
- [ ] Unparsed input is annotated `object` or `Mapping[str, object]`, not `Any` or an unchecked `TypedDict`
- [ ] Cross-field constraints are invariants of a composite type, not checks in one function that needed them
- [ ] Specifications and schemas are decoded into validated types at load; consumers do not re-check
- [ ] A malformed document raises a typed error naming the path and field, never a bare `KeyError` or
      `AttributeError`
- [ ] Downstream functions contain zero re-validation of what the boundary guaranteed
- [ ] Unit and convention conversions (`str` to `Path`, 1-based to 0-based) happen once, at the boundary
- [ ] Checks that require external state stay in the domain

## References

- [principle-least-surprise](principle-least-surprise.md) - Related: A function whose parameter is a parsed
  type must behave as though it trusts it
- [principle-information-hiding](principle-information-hiding.md) - Related: The parsed type hides the
  invariant its boundary established, so no caller has to know it

## External References

- [Parse, Don't Validate](https://lexi-lambda.github.io/blog/2019/11/05/parse-don-t-validate/)
- [Using Types To Guarantee Domain Invariants](https://lpalmieri.com/posts/2020-12-11-zero-to-production-6-domain-modelling/)
- [Architecture Patterns with Python (O'Reilly)](https://www.oreilly.com/library/view/architecture-patterns-with/9781492052197/)
