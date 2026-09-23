---
name: "python-dataclasses"
description: "Choosing between `@dataclass` and pydantic `BaseModel`, mutable defaults, avoiding set-later `None`, `frozen=True` for value records, `__post_init__` range checks, and the `Attributes:` contract. Load when declaring a config record, a value object, or a wire-boundary model"
type: "core"
scope: "global"
---

# Structured Records

A record declares the values something needs and the relationships between them. The whole benefit is that a
reader can take the declaration at face value: every attribute listed is present, its type is what it says, and
its value is in range. A record that needs a second call before it is usable, or that can be constructed with a
meaningless number in it, has given that benefit back.

Validation cost is the axis that separates the two tools available (§1). What the fields are annotated with is
owned by [python-typing](python-typing.md); what they are called is owned by
[python-naming](python-naming.md).

## 1. `@dataclass` for Internal Records, `BaseModel` at a Wire Boundary

`@dataclass` is the default for anything constructed inside the process: configuration records, value objects,
progress and result structures, anything on a per-document path. A pydantic `BaseModel` is used where
untrusted data enters — a parsed frontmatter block, a JSON Schema loaded from disk, a user-supplied checker
config file.

Pydantic validates on **every** construction. That is precisely what is wanted once, at the edge, where the
alternative is a hand-written check of every field; and it is pure overhead on a record built per finding,
where the values came from code that already knows their types. Putting a `BaseModel` on a hot path buys
nothing and costs a full validation pass per finding.

```python
# ❌ Bad — a per-finding record paying full field validation on every construction; a
# corpus check emits one per violated rule per document, and every one of them re-checks
# types that no caller could get wrong
class Finding(BaseModel):
    document: str
    line: int
    message: str
```

```python
# ✅ Good — internal record, no validation cost
@dataclass
class Finding:
    document: str
    line: int
    message: str


# ✅ Good — wire boundary, where validation is the point
class RuleFrontmatter(BaseModel):
    corpus: str
    name: str
    description: str
    scope: str
```

The boundary is where the data arrives from outside, not where it is first used. Validating deep in the call
stack means the untrusted value travelled through several frames first.

## 2. Generated Models Are Never Hand-Edited

Models produced from a JSON Schema are regenerated from that schema, never patched in place. A change to one
is a change to the schema followed by a regeneration, in the same commit.

A hand edit survives exactly until the next generation run, which silently reverts it — and because the
generated file is excluded from linting, nothing flags the divergence in between. The window where the model
disagrees with the schema it describes is the window where a frontmatter field is decoded into the wrong
shape.

Adding behaviour to a generated model is the same mistake in a friendlier form: put the helper in a module
beside the generated file and have it take the model as an argument.

```python
# ❌ Bad — a convenience property added to a generated model. It disappears on the next
# regeneration, and every call site breaks at once with an AttributeError on a field
# that is visibly present in the file they are reading
class RuleFrontmatter(BaseModel):
    corpus: str
    name: str

    @property
    def qualified_name(self) -> str:
        return f'{self.corpus}/{self.name}'
```

```python
# ✅ Good — the helper lives beside the generated module and takes the model
def qualified_name(frontmatter: RuleFrontmatter) -> str:
    """Return the ``corpus/name`` identifier for a rule document."""
    return f'{frontmatter.corpus}/{frontmatter.name}'
```

## 3. Mutable Defaults Use `field(default_factory=...)`

A field defaulting to a list, dict, or set is declared `field(default_factory=list)`. A bare `= []` is a
`ValueError` at class definition, and the workaround people reach for — a module-level constant shared as the
default — is the same bug without the error.

```python
# ❌ Bad — every config built without an explicit value shares one list object, so
# skipping a rule for one corpus skips it for every other corpus checked in the process
_NO_SKIPS: list[str] = []


@dataclass
class CheckerConfig:
    corpus: str
    skipped_rules: list[str] = _NO_SKIPS
```

```python
# ✅ Good — each instance gets its own list
@dataclass
class CheckerConfig:
    corpus: str
    skipped_rules: list[str] = field(default_factory=list)
    section_budgets: dict[str, int] = field(default_factory=dict)
```

An immutable default (`0`, `''`, `None`, a `frozen` record) is written directly; `default_factory` is for
values that could be mutated in place.

## 4. No `Optional` Stands In For "Set Later"

A field is not `X | None` because it gets populated by a later call. Optionality in the type means "this value
may legitimately be absent, and every reader must handle that".

A set-later field makes every read a question the type cannot answer: is this `None` because the caller has not
loaded the corpus yet, or because there genuinely is no value? Every method that touches it either checks or
gambles, and the check is the same three lines repeated down the class. The optionality belongs in the
construction path — build the record when the value exists, or keep the not-yet-ready state in a separate
object.

```python
# ❌ Bad — three fields that are None until `load()`, so every method starts with a
# guard, and the one method that forgets fails with an AttributeError on NoneType
# somewhere inside the per-document loop instead of at the call that skipped load
@dataclass
class CorpusCheck:
    config: CheckerConfig
    spec: FormatSpec | None = None
    schema: Schema | None = None
    documents: list[Document] | None = None
```

```python
# ✅ Good — the check exists only once it can do its job, so nothing downstream checks;
# the not-yet-loaded state is the absence of a CorpusCheck, held by the caller
@dataclass
class CorpusCheck:
    config: CheckerConfig
    spec: FormatSpec
    schema: Schema
    documents: list[Document]


def open_corpus_check(config: CheckerConfig) -> CorpusCheck:
    spec = load_format_spec(config.corpus)
    return CorpusCheck(
        config=config,
        spec=spec,
        schema=load_schema(spec),
        documents=load_documents(config.corpus),
    )
```

```python
# 🔶 Acceptable — genuinely absent, not deferred: a rule document that specializes
# nothing has no parent, and every reader must decide what to do about that
@dataclass
class RuleDocumentRef:
    corpus: str
    name: str
    parent: str | None = None
```

## 5. `frozen=True` for a Value Compared or Keyed

A record that is compared, put in a set, used as a dict key, or passed around as an identity is
`@dataclass(frozen=True)`. A mutable record used that way is a latent corruption: mutating a field after
insertion leaves the object in a bucket its new hash does not belong to, and it stops being findable by a
lookup with an equal value.

```python
# ❌ Bad — unhashable, so it cannot key the cache it was written for; made hashable with
# `eq=False` it would key on identity, and two equal spans would miss each other
@dataclass
class LineSpan:
    start: int
    end: int


_section_cache: dict[LineSpan, Section] = {}
```

```python
# ✅ Good — frozen, so `__hash__` is generated and the value is safe as a key
@dataclass(frozen=True)
class LineSpan:
    start: int
    end: int


_section_cache: dict[LineSpan, Section] = {}
```

A configuration record read by long-lived components is a good candidate too: freezing it makes "someone
mutated the config halfway through a run" impossible instead of merely unlikely. A record that is a mutable
accumulator — a findings buffer, a running counter — is not frozen, and is not a dict key either.
[pattern-value-object](pattern-value-object.md) owns the fuller treatment.

## 6. A Numeric Limit Validates in `__post_init__`

A field with a meaningful range — a line budget, a heading depth, a finding limit, a line number — is checked
in `__post_init__` and raises `ValueError` naming the field and the offending value.

The check is **mandatory, not optional**, and the reason is that Python offers nothing stronger. In a
type-driven design the constraint would live in the type, so an out-of-range value would be unconstructible and
no runtime check would be needed. Here the annotation is `int`, and `int` includes `-1`; the guarantee is
weaker than a type-level one, and `__post_init__` is the only place it can be recovered. Skipping it does not
trade a check for a stronger guarantee — it trades a check for none.

```python
# ❌ Bad — `max_lines=0` puts every document over budget and `warn_ratio=-1` warns on
# every section, so a corpus check reports a finding per document and the genuinely
# over-budget ones are lost in the noise. Both are constructible and neither is meant
@dataclass
class LengthBudget:
    max_lines: int = 400
    warn_ratio: float = 0.9
```

```python
# ✅ Good — the impossible values are rejected at construction, where the traceback
# points at the caller that supplied them
@dataclass
class LengthBudget:
    max_lines: int = 400
    warn_ratio: float = 0.9

    def __post_init__(self) -> None:
        """Validate budget bounds.

        Raises:
            ValueError: If ``max_lines`` is below 1 or ``warn_ratio`` is outside ``(0, 1]``.
        """
        if self.max_lines < 1:
            raise ValueError(f'max_lines must be at least 1, got {self.max_lines}')
        if not 0 < self.warn_ratio <= 1:
            raise ValueError(f'warn_ratio must be in (0, 1], got {self.warn_ratio}')
```

The message includes the value. `ValueError('invalid max_lines')` sends the reader back to the call site to
find out what was passed; the value in the message ends the investigation.

Cross-field relationships belong here too — a line span whose `end` precedes its `start` is one check, not two
field checks.

## 7. `Attributes:` in the Class Docstring Is the Record's Contract

A record's docstring opens with a one-line summary and lists every public field under `Attributes:`, each with
its meaning, its unit, and any constraint `__post_init__` enforces.

The annotation gives the type; the docstring gives everything the type cannot. `budget: int` does not say
lines or words, and `max_depth: int` does not say whether the H1 counts as level one. That information is
otherwise discovered by reading the consumer.

```python
# ❌ Bad — is the budget counted in lines or words? Does `max_depth` start at the H1 or
# at the first numbered section? A caller picks wrong and the symptom is a check that
# either never reports a section or reports every one of them
@dataclass
class OutlineCheckConfig:
    """Outline checking configuration."""

    corpus: str
    max_depth: int = 3
    budget: int = 400
```

```python
# ✅ Good — units and bounds stated where the caller reads them
@dataclass
class OutlineCheckConfig:
    """Configuration for checking a corpus against its structure specification.

    Attributes:
        corpus: Corpus name, matching the format specification that governs it.
        max_depth: Deepest heading level checked, counting the H1 as level 1.
            Must be at least 1.
        budget: Prose length budget per document, in lines. Must be at least 1; there is
            no unbounded setting.
    """

    corpus: str
    max_depth: int = 3
    budget: int = 400
```

Docstring form beyond this — sections, wording, when a method needs one — is owned by
[python-docstrings](python-docstrings.md).

## Checklist

Before committing code, verify:

- [ ] Every new record is a `@dataclass` unless it decodes data arriving from outside the process, in which
      case it is a `BaseModel`
- [ ] No generated model file is edited by hand, and no helper or property was added to one
- [ ] Every list, dict, or set default uses `field(default_factory=...)`; no module-level mutable is used as a
      default
- [ ] No field is `X | None` merely because it is assigned after construction; each optional field is one that
      can legitimately be absent
- [ ] Every record used as a dict key, set member, or compared identity is `frozen=True`
- [ ] Every field with a meaningful numeric range has a `__post_init__` check raising `ValueError` with the
      field name and the received value
- [ ] Every record's class docstring lists all public fields under `Attributes:` with units and constraints

## References

- [pattern-value-object](pattern-value-object.md) - Related: The frozen, compared-by-value record §5
  describes, in full
- [principle-least-surprise](principle-least-surprise.md) - Foundation: Why a constructed record must be
  usable without a follow-up call
- [python-typing](python-typing.md) - Related: Field annotation spelling, including `X | None` and quoted
  forward references
- [python-naming](python-naming.md) - Related: Field and class naming, and `ClassVar` capability constants
- [python-docstrings](python-docstrings.md) - Related: Docstring sections beyond `Attributes:`
- [python-exceptions](python-exceptions.md) - Related: When a validation failure warrants a domain
  exception rather than `ValueError`

## External References

- [dataclasses - Python Standard Library](https://docs.python.org/3/library/dataclasses.html)
- [Google Python Style Guide - Comments and Docstrings](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings)
