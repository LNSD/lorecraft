---
name: "python-docstrings"
description: "Google-style docstrings: which constructs carry one, when Args/Returns earn their lines, mandatory Raises, and whether an Example block is a doctest. Load when adding or editing a docstring, when a function grows a new exception path, or when deciding whether a parameter needs prose"
type: "core"
scope: "global"
---

# Google-Style Docstrings

A docstring says what a caller gets and what a caller must uphold, in the timeless present. Everything else —
why the code is shaped this way, what it used to be, the argument for an exception — belongs in a `#` comment
beside the line that needs it. Log lines are owned by [logging](logging.md); the error types a `Raises:`
section names are owned by [python-exceptions](python-exceptions.md); the annotations a docstring
deliberately does not restate are owned by [python-typing](python-typing.md).

**This document keeps `Args:` and `Returns:`, against a real argument for dropping them.** That argument is
that the reader is holding the signature: the parameter names are visible, the return type is visible, and a
section restating them is a second place for the same fact to rot. The premise is weaker in Python.
Annotations are absent or `Any` across a large share of signatures, nothing checks them, and `Args:` is what
every Python reader and every tool already expects. So both sections stay — together with the discipline that
made the argument against them attractive: never a paragraph per parameter, never a restatement of the type,
and a parameter that needs a paragraph needs a better name or a value object
([pattern-value-object](pattern-value-object.md)) instead of a docstring apologising for it.

## 1. Google Style, and Only Google Style

Every docstring is a triple-quoted block in Google style: a one-line summary, a blank line, optional prose,
then the named sections `Args:`, `Returns:`, `Yields:`, `Raises:`, `Attributes:`, `Example:`. reStructuredText
field lists (`:param x:`), NumPy underlined sections, and Epytext (`@param`) are not written, and are
converted when touched.

One style across a codebase is worth more than the merits of any of them: mixed styles mean a reader parses
the format before the content, and no renderer produces a coherent page from three of them.

```python
# ❌ Bad — reST field list in a Google-style corpus; the reader parses the syntax before the meaning
def render_report(self, findings, corpus_name):
    """Render one corpus's findings as a report.

    :param findings: the findings
    :type findings: list[Finding]
    :param corpus_name: the corpus
    :returns: lines written
    """
```

```python
# ✅ Good — Google sections, summary first, types left to the annotations
def render_report(self, findings: list[Finding], corpus_name: str) -> int:
    """Render one corpus's findings as a report.

    Args:
        findings: Findings to render. Order is not significant; they are grouped by document.
        corpus_name: Title the report is written under. Matched against the corpus directory name.

    Returns:
        Lines written, which may be fewer than `len(findings)` when several findings on one
        document collapse into a single line.
    """
```

**Enforcement:** ruff `D` with `convention = "google"` — not currently enabled; see the checklist.

## 2. Every Module, Class, and Public Function Carries a Docstring

A module docstring says why the module exists and what it defends against. A class docstring says what the
class is responsible for. A public function docstring says what calling it gives you. A private helper carries
one when its contract is not obvious from its name and body; a two-line `_normalise_heading` does not.

The module docstring is the one a reader reaches for first and the one most often missing. It is also the only
place an invariant spanning several functions can live — "section spans in this module are half-open" is a
fact about the file, not about any one signature.

```python
# ❌ Bad — restates the module name and teaches the next editor nothing
"""Outline handling module."""
```

```python
# ✅ Good — says why the module exists and states the invariant its functions rely on
"""Match a document's heading outline against the structure specification for its corpus.

A section runs from its own heading to the next heading at the same level or above. Spans
here are half-open (`start` inclusive, `end` exclusive) so that the last section ends at
`end = len(lines)` without an off-by-one at the seam.
"""
```

**Enforcement:** ruff `D100`–`D107` under `convention = "google"`, narrowed to the missing-docstring codes plus
the `D2xx` formatting codes; `D401` (imperative mood) is deliberately excluded as too noisy for the gain — not
currently enabled; see the checklist.

## 3. `Args:` Only Where the Name Does Not Already Say It

A parameter earns an `Args:` line when the line carries something the name and annotation do not: a unit, a
bound, a default's meaning, an ownership or mutation note, or what happens when it is omitted. A parameter
whose name says everything gets no line, and a docstring may list some parameters and not others.

Never restate the type — the annotation is already there and the two copies will disagree. Never write a
paragraph per parameter. A parameter that genuinely needs a paragraph is a parameter whose meaning belongs in
its type ([pattern-value-object](pattern-value-object.md)) or whose name is wrong.

```python
# ❌ Bad — one paragraph per parameter, each restating the annotation, none adding a fact
def iter_sections(self, document: str, first_line: int, last_line: int, line_budget: int = 110):
    """Iterate sections.

    Args:
        document: A string containing the name of the document whose sections should be
            walked. This is the document name as a Python string value.
        first_line: An integer representing the first line.
        last_line: An integer representing the last line.
        line_budget: An integer representing the line budget.
    """
```

```python
# ✅ Good — only the facts no signature carries: the half-open bound, and the default's real effect
def iter_sections(self, document: str, first_line: int, last_line: int, line_budget: int = 110) -> Iterator[Section]:
    """Walk a document's sections in reading order.

    Args:
        last_line: Exclusive. `first_line == last_line` yields nothing.
        line_budget: Columns a prose line may occupy before it is reported. Table rows and
            fenced code are measured but never reported against it.
    """
```

## 4. `Returns:` Only Where the Shape Is Not Obvious

`Returns:` is written when the annotation leaves a question: what the elements of a `dict[str, Any]` are keyed
by, what a bare `int` counts, what ordering a sequence carries, what `None` means as a return rather than as a
failure. A `-> None`, a `-> bool` whose name says what it answers, and a `-> StructureSpec` whose type is the
answer get no section.

The test is whether a caller could be surprised by the value while looking straight at the annotation. If not,
the section is noise that survives until the signature changes and then becomes wrong.

```python
# ❌ Bad — restates the annotation; the sentence is already spelled `-> bool` above it
def has_frontmatter(self, document: str) -> bool:
    """Check whether a document carries frontmatter.

    Returns:
        bool: True if the document has frontmatter, False otherwise.
    """
```

```python
# ✅ Good — the annotation cannot say what the ints count or how the mapping is keyed
def findings_per_document(self, report: Report) -> dict[str, int]:
    """Count findings raised per document during the last completed check.

    Returns:
        Document name to findings raised. Documents the run skipped are absent rather than
        present with a zero.
    """
```

## 5. `Raises:` Is Mandatory on Anything That Raises

Every function that can raise documents each exception type a caller can reach, and the condition that
produces it. That includes exceptions raised directly and exceptions raised by a callee and allowed to
propagate as part of this function's contract.

This is the strongest rule in the document, because Python gives a caller **no other way to find out**. There
are no checked exceptions, no `Result` in the return type, and no compiler that notices the new `raise` you
added on line 40. A caller who does not know that loading a specification raises `MalformedSpecError` writes a
`try` block around the wrong call, or none at all, and a whole-corpus check dies on the first document whose
frontmatter drifted.

An exception the code's own invariants make unreachable is not documented — documenting a raise a caller
cannot trigger sends them writing handlers for it. Such a spot carries a `#` comment saying why it cannot
happen, at the line.

```python
# ❌ Bad — three reachable exception types, none documented; the caller learns them from a failed run
def load_spec(self, corpus: str) -> StructureSpec:
    """Load the structure specification for a corpus."""
```

```python
# ✅ Good — each type paired with the condition that reaches it
def load_spec(self, corpus: str) -> StructureSpec:
    """Load a corpus's structure specification, resolving the schema it names.

    Raises:
        SpecNotFoundError: No specification is declared for the corpus.
        MalformedSpecError: The specification's frontmatter is not valid YAML, or omits a
            field the format requires.
        SchemaResolutionError: The specification names a JSON Schema that cannot be read or
            does not parse. Nothing is cached; a later call retries.
    """
```

## 6. `Example:` Blocks Are Doctests

An `Example:` block is written as `>>>` doctest lines or it is not written. Free-form pseudo-code in a
docstring is a usage story that was true once, and a reader cannot tell which parts still are.

**Nothing executes them in this repository today.** The test suite runs without `--doctest-modules`, and no
other runner collects them, so an `Example:` block is prose that happens to look executable. A contract nobody
runs rots, silently, in the direction of looking correct. So there are exactly two honest positions, and the
document takes the second:

1. Turn doctests on, and treat every `Example:` as a test that must pass.
2. Until then, **assume every `Example:` block is illustrative, not verified** — write it as a doctest so it is
   ready for (1), keep it to a handful of lines, and never let it be the only statement of a contract. If a
   behaviour must be guaranteed, a test under `tests/` guarantees it
   ([test-organization](test-organization.md)).

An example that would need a corpus checked out on disk, a network fetch, or a fixture tree to run is not an
example; it is a test that has wandered into a docstring.

```python
# ❌ Bad — a usage story with invented output, unrunnable and unverifiable
def overlong_spans(lines: list[int]) -> list[tuple[int, int]]:
    """Group over-budget line numbers into contiguous spans.

    Example:
        spans = overlong_spans(lines)   # gives you the contiguous runs
        # -> something like [(12, 15), ...]
    """
```

```python
# ✅ Good — a real doctest: runnable the day `--doctest-modules` is enabled, honest prose until then
def overlong_spans(lines: list[int]) -> list[tuple[int, int]]:
    """Group sorted over-budget line numbers into half-open contiguous spans.

    Example:
        >>> overlong_spans([12, 13, 14, 19, 20])
        [(12, 15), (19, 21)]
    """
```

## 7. `Attributes:` Documents a Record's Contract

A dataclass, config object, or any class whose fields are part of its public surface documents them in an
`Attributes:` section, under the same rule as `Args:`: a field earns a line when the line carries a unit, a
bound, a default's meaning, or a relationship to another field. A field whose name is the whole story gets no
line.

A config record is read far more often than it is constructed, usually by someone deciding what to put in a
configuration file, and the class docstring is where they look. That reader has no call site to learn from and
no signature in front of them.

```python
# ❌ Bad — every field echoed, so the two constraints that matter are buried among restated types
@dataclass
class CheckConfig:
    """Check configuration.

    Attributes:
        line_budget: An integer, the line budget.
        max_findings_per_document: An integer, the max findings per document.
        fail_on_warning: A boolean, whether to fail on warning.
        corpus_root: A string, the corpus root.
    """
```

```python
# ✅ Good — only the fields with a constraint, a unit, or a dependency on another field
@dataclass(frozen=True, slots=True)
class CheckConfig:
    """Budgets and reporting limits for a single corpus check.

    Attributes:
        line_budget: Columns a prose line may occupy. Table rows and fenced code are
            measured but never reported against it.
        max_findings_per_document: Findings reported for one document before the rest are
            summarised as a count. Must be at least 1.
        spec_path: Structure specification to check against. Resolved relative to
            `corpus_root` when it is not absolute.
    """

    line_budget: int = 110
    max_findings_per_document: int = 20
    fail_on_warning: bool = False
    corpus_root: str = 'docs'
    spec_path: str | None = None
```

## Checklist

Before committing code, verify:

- [ ] Every docstring touched is Google style — no `:param:`, no `@param`, no NumPy underlines
- [ ] Every module added or edited has a docstring saying why it exists, not restating its name
- [ ] Every new class and public function has a docstring whose first line is a one-line summary
- [ ] No `Args:` line restates a parameter's type or expands its name into a paragraph
- [ ] Every `Args:` line present carries a unit, bound, default meaning, or omission behaviour
- [ ] No `Returns:` section restates the return annotation
- [ ] Every reachable `raise` in the diff — direct or propagated by contract — appears in a `Raises:` section
      with the condition that produces it
- [ ] An unreachable `raise` has a `#` comment saying why, and no `Raises:` entry
- [ ] Every `Example:` block is `>>>` doctest lines, not prose pseudo-code
- [ ] No `Example:` block is the sole statement of a contract that has no test
- [ ] No `Example:` block requires a checked-out corpus, a network fetch, or a fixture tree to run
- [ ] `Attributes:` lists only the fields carrying a unit, bound, default meaning, or cross-field dependency

## References

- [python-typing](python-typing.md) - Related: Owns the annotations a docstring deliberately does not restate
- [python-naming](python-naming.md) - Related: Owns the names that make an `Args:` line unnecessary
- [python-modules](python-modules.md) - Related: Owns module boundaries; this document owns the `"""` block at the top of one
- [python-exceptions](python-exceptions.md) - Related: Owns the exception types a `Raises:` section names
- [python-dataclasses](python-dataclasses.md) - Related: Owns the record whose fields an `Attributes:` section documents
- [pattern-value-object](pattern-value-object.md) - Related: The replacement for a parameter that needs a paragraph
- [test-organization](test-organization.md) - Related: Where a contract that must be guaranteed is actually guaranteed
- [logging](logging.md) - Related: Owns runtime narration, which is never a docstring's job
- [principle-least-surprise](principle-least-surprise.md) - Foundation: A `Raises:` section exists because Python cannot surprise a caller with an exception type any other way
- [principle-information-hiding](principle-information-hiding.md) - Foundation: A docstring states the contract, not the implementation behind it

## External References

- [Google Python Style Guide — Comments and Docstrings](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings)
- [PEP 257 — Docstring Conventions](https://peps.python.org/pep-0257/)
- [Python docs — `doctest`](https://docs.python.org/3/library/doctest.html)
- [Ruff — pydocstyle (`D`) rules](https://docs.astral.sh/ruff/rules/#pydocstyle-d)
