---
name: "python-docstrings"
description: "Google-style docstrings with Markdown prose: which constructs carry one, when Args/Returns earn their lines, mandatory Raises, and whether an Example block is a doctest. Load when adding or editing a docstring, when a function grows a new exception path, or when deciding whether a parameter needs prose"
type: "core"
scope: "global"
---

# Google-Style Docstrings

A docstring says what a caller gets and what a caller must uphold, in the timeless present. Everything else —
why the code is shaped this way, what it used to be, the argument for an exception — belongs in a `#` comment
beside the line that needs it. Log lines are owned by [logging](logging.md); the error types a `Raises:`
section names are owned by [error-types](error-types.md); the annotations a docstring
deliberately does not restate are owned by [python-typing](python-typing.md).

**`Args:` and `Returns:` stay, though the signature is in front of the reader.** A rendered page or a hover
shows the docstring, and a section is only worth its lines when it says what the annotation cannot: never
the type again, never a paragraph per parameter.

## 1. Google Sections, Markdown Prose

Every docstring is a triple-quoted block in Google style, its sections in this order:

| Section | Written when | Rule |
|---|---|---|
| Summary | Always | §1 |
| Prose | The summary leaves a contract unsaid | §2 |
| `Note:` / `Warning:` | A caveat the reader must not miss | §1 |
| `Args:` | The function takes a parameter; a line for every one | §3 |
| `Returns:` | A function `return`s a value its annotation does not fully explain | §4 |
| `Yields:` | A generator, a body holding `yield`, in place of `Returns:` | §4 |
| `Raises:` | The function, or a class's constructor, can raise; every reachable type | §5 |
| `Attributes:` | A class's fields are public | §7 |
| `Example:` | A doctest helps | §6 |

A function, with every section a function can have:

```python
def split_frontmatter(text: str, *, delimiter: str = '---') -> tuple[str | None, str]:
    r"""Split a Markdown document into its frontmatter block and its body.

    The block is returned as text, not decoded: a YAML error belongs to the caller that parses it, so a
    document whose YAML is broken still gives a body every structure check can read.

    Warning:
        Only a delimiter on the **first** line opens a block. A `---` thematic break further down is body.

    Args:
        text: The whole document as read from disk; line endings may be `\n` or `\r\n`.
        delimiter: Line that opens and closes the block, matched on the whole line with trailing
            whitespace ignored.

    Returns:
        `(frontmatter, body)`. `frontmatter` excludes both delimiter lines, and is `''` for an empty
        block but `None` when the document opens with no delimiter, in which case `body` is `text`.

    Raises:
        UnterminatedFrontmatterError: If the opening delimiter has no closing one.

    Example:
        >>> split_frontmatter('---\nname: "logging"\n---\n# Logging\n')
        ('name: "logging"', '# Logging\n')
        >>> split_frontmatter('# Logging\n')
        (None, '# Logging\n')
    """
```

A class, with every section a class can have, and the members a value object usually carries:

```python
@dataclass(frozen=True, slots=True, order=True)
class LineSpan:
    """A half-open run of a document's lines: where a finding is reported.

    Lines are 1-based, as an editor and `path:line` output show them, so the span over the first line
    alone is `LineSpan(1, 2)`. A span never refers back to the document it was cut from.

    Note:
        Spans order by `start`, then `end`, so sorting findings by span gives reading order.

    Raises:
        InvalidSpanError: On construction, if `start` is below 1 or `end` is below `start`.

    Attributes:
        start: First line in the span, inclusive.
        end: Line after the last one, exclusive. Equal to `start` for an empty span, the position
            between two lines where a missing section would go.

    Example:
        >>> LineSpan.parse('12-14')
        LineSpan(start=12, end=15)
    """

    start: int
    end: int

    def __post_init__(self) -> None:
        if self.start < 1 or self.end < self.start:
            raise InvalidSpanError(self.start, self.end)

    @classmethod
    def parse(cls, text: str) -> 'LineSpan':
        """Parse an inclusive range as a user types it, `12` or `12-14`.

        Args:
            text: One line number, or the first and last joined by `-`, with no spaces.

        Returns:
            The span over those lines, both ends included: `12-14` covers three.

        Raises:
            InvalidSpanError: If `text` is not one or two positive integers, or its last line precedes
                its first.
        """

    @property
    def lines(self) -> int:
        """Lines the span covers; 0 for an empty span."""
        return self.end - self.start

    def contains(self, line: int) -> bool:
        """Whether `line` falls inside the span.

        Args:
            line: 1-based line number, as the bounds are.
        """
        return self.start <= line < self.end
```

`__post_init__` has no docstring: what it refuses is the class's `Raises:`. `contains` has no `Returns:`:
its name and `-> bool` already say what it answers.

A section a docstring does not need is left out; the rest keep the table's order. A summary-only docstring is
one line, quotes included. reST field lists (`:param x:`), NumPy underlines and Epytext (`@param`) are
converted when touched.

All prose inside is Markdown: single backticks for code, `**bold**` for the one fact a reader must not skim
past, `-` lists, fenced blocks. No reST inline markup — double-backtick literals, `:class:` roles, `.. note::`
directives — which is converted when the docstring is touched.

Mixed styles make a reader parse the format before the content. Google sections with Markdown prose is the
pair `mkdocstrings` renders as is; no documentation site is built today, but the docstrings are ready for one.

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

The two examples above are the Good side of this pair.

**Enforcement:** ruff `D` with `convention = "google"` holds the layout. Nothing checks the Markdown; review
does.

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
"""Match a document's heading outline against the structure file for its corpus.

A section runs from its own heading to the next heading at the same level or above. Spans
here are half-open (`start` inclusive, `end` exclusive) so that the last section ends at
`end = len(lines)` without an off-by-one at the seam.
"""
```

A test module carries a docstring saying what it pins; a test class or function does not, since its name
already says what it checks ([tests-functions](tests-functions.md)). An `__init__` needs none: the class
docstring states what constructing it takes; one that has a docstring follows §3. A magic method carries one
too, saying what this class's version gives: what a `__str__` prints, what a `__lt__` orders by.

## 3. `Args:` Describes Every Parameter, Meaningfully

A function or method that carries a docstring and takes a parameter has an `Args:` section with a line for
every parameter, `self` and `cls` aside, keyword-only, `*args` and `**kwargs` included. The reader of a
rendered page or a hover has the docstring, not the body, and a missing line leaves them guessing. A Typer
command's parameters and its `--help` are owned by [python-typer](python-typer.md).

A line says what the parameter is **to this call**: the role it plays, and where it applies, its unit, its
bound, what its default means, whether it is mutated or kept, and what happens when it is omitted or empty.
A line that only echoes the name (`frontmatter: The frontmatter.`) or restates the annotation is not a
description, and fails review as surely as a missing one. Never write a paragraph per parameter: a parameter
that needs one belongs in a type ([pattern-value-object](pattern-value-object.md)) or has the wrong name.

**Enforcement:** ruff `D417` fails a docstring whose `Args:` omits a parameter. It does not fire on a
docstring with no `Args:` at all, nor tell a meaningful line from an echo; review catches both.

```python
# ❌ Bad — two parameters missing, and the lines present only restate the annotation
def iter_sections(self, document: str, first_line: int, last_line: int, line_budget: int = 110):
    """Iterate sections.

    Args:
        document: A string containing the name of the document.
        last_line: An integer representing the last line.
    """
```

```python
# ✅ Good — every parameter, each line a fact the signature does not carry
def iter_sections(self, document: str, first_line: int, last_line: int, line_budget: int = 110) -> Iterator[Section]:
    """Walk a document's sections in reading order.

    Args:
        document: Name of the document to walk, as the corpus lists it.
        first_line: First line to walk, 1-based and inclusive.
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

Which of the two a function writes follows from its body, not its annotation. A generator, any body holding
`yield`, writes `Yields:`, describing **one** value `next()` gives, and never `Returns:`, even though calling
it returns an iterator. A function that `return`s an iterator it built, `iter(spans)` or a generator
expression, is not a generator and writes `Returns:`. The same test decides whether either is written at all.

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
propagate as part of this function's contract. An error union is not an exception type: the section lists
each of its variants, since a variant is what a caller names in an `except`. Whether a built-in belongs there
at all is owned by [error-boundaries](error-boundaries.md): a propagated one `error-boundaries` §2 has not
cleared is a finding against its source, not a line to add.

This is the strongest rule here, because Python gives a caller **no other way to find out**: no
checked exceptions, no `Result` in the return type. A caller who does not know that loading a meta spec
raises `MalformedSpecError` guards the wrong call, and a whole-corpus check dies on the first drifted document.

An exception the code's invariants make unreachable is not documented — documenting a raise a caller
cannot trigger sends them writing needless handlers. Such a spot carries a `#` comment saying why it cannot
happen, at the line.

```python
# ❌ Bad — three reachable exception types, none documented; the caller learns them from a failed run
def load_spec(self, corpus: str) -> StructureSpec:
    """Load the structure file for a corpus."""
```

```python
# ✅ Good — each type paired with the condition that reaches it
def load_spec(self, corpus: str) -> StructureSpec:
    """Load a corpus's structure file, resolving the schema it names.

    Raises:
        SpecNotFoundError: No meta spec is declared for the corpus.
        MalformedSpecError: The meta spec's frontmatter is not valid YAML, or omits a
            field the format requires.
        SchemaResolutionError: The meta spec names a JSON Schema that cannot be read or
            does not parse. Nothing is cached; a later call retries.
    """
```

## 6. `Example:` Blocks Are Doctests

An `Example:` block is written as `>>>` doctest lines or it is not written. Free-form pseudo-code in a
docstring is a usage story that was true once, and a reader cannot tell which parts still are.

**Nothing executes them in this repository today**: the suite runs without `--doctest-modules`. So every
`Example:` block is **illustrative, not verified** — written as a doctest so it is ready the day doctests are
turned on, kept to a handful of lines, and never the only statement of a contract. A behaviour that must be
guaranteed is guaranteed by a test ([tests-organization](tests-organization.md)).

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

A dataclass, config object, error variant ([error-types](error-types.md)) or other class with public fields
lists **every** one under `Attributes:`. Only a field with a leading underscore, a pydantic model's field
(its docstring sits under it) and a base's class constants are left out. As in `Args:`, a line says
the field's role and, where they apply, its unit, bound, default's meaning and tie to another field. An
echo of the name or type fails review: a record's reader has no call site to learn from.

```python
# ❌ Bad — fields missing, and each line echoes its name and type
@dataclass
class CheckConfig:
    """Check configuration.

    Attributes:
        line_budget: An integer, the line budget.
        fail_on_warning: A boolean, whether to fail on warning.
    """
```

```python
# ✅ Good — every field, each line a fact its annotation does not carry
@dataclass(frozen=True, slots=True)
class CheckConfig:
    """Budgets and reporting limits for a single corpus check.

    Attributes:
        line_budget: Columns a prose line may occupy. Table rows and fenced code are
            measured but never reported against it.
        max_findings_per_document: Findings reported for one document before the rest are
            summarised as a count. Must be at least 1.
        fail_on_warning: Whether a warning fails the check; when false it is only reported.
        corpus_root: Corpus directory, relative to the workspace root.
        spec_path: Structure file to check against. Resolved relative to
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

- [ ] Every docstring touched is Google style: no `:param:`, `@param` or NumPy underlines
- [ ] Its sections run `Note:`/`Warning:`, `Args:`, `Returns:`/`Yields:`, `Raises:`, `Attributes:`, `Example:`
- [ ] Its prose is Markdown: single backticks, no double-backtick literals, reST roles or directives
- [ ] Every module touched has a docstring saying why it exists, not restating its name
- [ ] Every new class and public function has a docstring opening with a one-line summary
- [ ] Every docstring of a function taking a parameter has `Args:`, a line per parameter
- [ ] Every `Args:` line says what the parameter is to the call, never its name or type echoed, nor a paragraph
- [ ] No `Returns:` section restates the return annotation
- [ ] A generator documents `Yields:`, never `Returns:`; a function returning an iterator documents `Returns:`
- [ ] Every reachable `raise` in the diff, direct or propagated by contract, is in `Raises:` with its condition;
      a propagated built-in failing `error-boundaries` §2 is fixed at its source
- [ ] An unreachable `raise` has a `#` comment saying why, and no `Raises:` entry
- [ ] Every `Example:` block is `>>>` doctest lines, never the sole statement of an untested contract
- [ ] No `Example:` block needs a checked-out corpus, a network fetch, or a fixture tree to run
- [ ] `Attributes:` has a line for every field, saying what its annotation cannot, never its name echoed

## References

- [python-typing](python-typing.md) - Related: Owns the annotations a docstring deliberately does not restate
- [python-naming](python-naming.md) - Related: Owns the names an `Args:` line builds on
- [python-modules](python-modules.md) - Related: Owns module boundaries; this document owns the `"""` block at the top of one
- [error-types](error-types.md) - Related: Owns the error types a `Raises:` section names
- [error-boundaries](error-boundaries.md) - Related: Owns whether a built-in belongs in `Raises:`
- [python-dataclasses](python-dataclasses.md) - Related: Owns the record whose fields an `Attributes:` section documents
- [pattern-value-object](pattern-value-object.md) - Related: The replacement for a parameter that needs a paragraph
- [tests-organization](tests-organization.md) - Related: Where a contract that must be guaranteed is actually guaranteed
- [logging](logging.md) - Related: Owns runtime narration, which is never a docstring's job
- [principle-least-surprise](principle-least-surprise.md) - Foundation: A `Raises:` section exists because Python cannot surprise a caller with an exception type any other way
- [principle-information-hiding](principle-information-hiding.md) - Foundation: A docstring states the contract, not the implementation behind it

## External References

- [Google Python Style Guide — Comments and Docstrings](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings)
- [PEP 257 — Docstring Conventions](https://peps.python.org/pep-0257/)
- [Python docs — `doctest`](https://docs.python.org/3/library/doctest.html)
- [Ruff — pydocstyle (`D`) rules](https://docs.astral.sh/ruff/rules/#pydocstyle-d)
- [Griffe — Google-style docstrings](https://mkdocstrings.github.io/griffe/reference/docstrings/#google-style), the parser `mkdocstrings` renders them with
