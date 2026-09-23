---
name: "principle-least-surprise"
description: "Principle of Least Surprise — code behaves as its name, signature and shape predict, following the Python standard library and this package's settled vocabulary (connect/disconnect for lifecycle), so that a name predicts behaviour, cost and failure, a property never performs I/O, the dunders mean what the language says they mean, and a function named for a computation never also writes; deviations are documented at the declaration. Load when naming a function or class, designing a constructor or lifecycle pair, adding a property or a dunder, or reviewing an API surface"
type: "principle"
scope: "global"
---

# Principle of Least Surprise

## Rule

Code must behave the way a reader predicts from its name, signature, and shape. A name is a contract: what a
function returns, what it touches, what it costs, and whether it can fail should be guessable without opening
it. **The Python standard library is the first reference, and this package's own settled vocabulary is the
second** — once a word is used consistently here, it wins over a synonym imported from elsewhere. The
conventions:

1. **A name predicts behaviour, cost, and failure.** `document_names()` returns names cheaply.
   `load_document_names()` goes to the filesystem and can fail. A name that hides a directory walk or a
   re-parse of every document in the corpus has mispriced itself, and callers will put it in a loop.
2. **Construction reveals its cost.** `__init__` does not connect, spawn, or read. A type that must touch the
   filesystem before it is usable is built by a named `classmethod` — `connect` — so no instance is ever
   observably half-initialised and no method needs a readiness guard.
3. **Lifecycle is `connect`/`disconnect`.** That pair is settled in this package. Not `close`, not `shutdown`,
   not `stop`: the standard library's own `close` is the more common word in the wider world, and the repo's
   consistent vocabulary beats it here precisely because consistency is what makes prediction possible.
   `disconnect` is safe to call twice and safe to call on an instance that never connected.
4. **Paired names.** If the package uses `parse`/`render`, do not introduce `read`/`emit`. The inverse of `add`
   is `remove`, not `delete_item`.
5. **A property that does I/O is a lie.** Attribute syntax promises a field read. Debuggers, `repr`, and
   f-strings in log calls evaluate properties without anyone deciding to; a property that re-reads a file turns
   a logging statement into a per-document round trip. Anything that reads, parses, or blocks is a method whose
   name says so.
6. **Dunders mean what the language says.** `__len__` is cheap and exact, so it does not drain a stream or walk
   a corpus directory. `__iter__` yields the elements and may be called more than once, or the type is a
   one-shot iterator and says so. `__eq__` covers the fields that make up identity, and anything hashable
   keeps `__hash__` consistent with it.
7. **Parameters.** More than two or three related inputs go in a dataclass or a settings object, never a
   positional `bool`. `check(document, spec, True, False)` cannot be reviewed.
8. **No hidden effects.** A function named for a computation does not write a report, open a file, or mutate
   module state. Where a lookup and an effect both exist, they are two functions.

## Examples

1. **`__init__` does not connect; `connect`/`disconnect` are the lifecycle pair**
   A type that needs an open corpus before any method works cannot be built by a plain constructor.

```python
# ❌ Bad — the constructor starts the corpus scan in a background thread and returns
# immediately. Every method then needs a "has the scan finished yet?" guard, and the caller
# who forgets one gets an AttributeError on None from inside a loop over documents, three
# frames below where it was built.
class CorpusIndex:
    def __init__(self, root: Path) -> None:
        self._root = root
        self._documents: dict[str, Document] | None = None
        threading.Thread(target=self._scan, daemon=True).start()

    def document(self, name: str) -> Document:
        if self._documents is None:
            raise NotConnectedError('index is still scanning')  # ...on every method
        return self._documents[name]
```

```python
# ✅ Good — the named constructor completes the scan and hands back an index that is, by
# construction, usable; the inverse is named for the same thing and is safe to repeat.
class CorpusIndex:
    @classmethod
    def connect(cls, root: Path) -> 'CorpusIndex':
        """Read every document under ``root`` and return a ready index.

        Args:
            root: Directory holding the corpus documents.

        Returns:
            An index whose documents are loaded.

        Raises:
            CorpusError: If the corpus root cannot be read.
        """
        return cls(scan_corpus(root))

    def document(self, name: str) -> Document:
        return self._documents[name]

    def disconnect(self) -> None:
        """Release every open document handle. Safe to call on a disconnected index."""
        if self._documents is not None:
            release_all(self._documents)
            self._documents = None
```

2. **A property reads a field; a parse is a method**
   Attribute syntax sets the price the caller expects to pay.

```python
# ❌ Bad — attribute syntax over a file read and a full section parse. The debug log below
# runs once per document, so checking a corpus of six hundred rule documents re-reads and
# re-parses every one of them just to build a log line, and nobody reading the log can see
# why the run takes minutes.
class RuleDocument:
    @property
    def section_count(self) -> int:
        return len(parse_sections(self._path.read_text(encoding='utf-8')))


logger.debug(f'checked {document.name} (has {document.section_count} sections)')
```

```python
# ✅ Good — the cheap field stays a property; the parse is a method whose name and docstring
# price it, and the log line reports what the check already knew.
class RuleDocument:
    @property
    def name(self) -> str:
        return self._name

    def count_sections(self) -> int:
        """Count the headings in the document body.

        Returns:
            The number of sections. This re-reads and re-parses the file; do not call it
            once per check.

        Raises:
            ParseError: If the document body cannot be parsed.
        """
        return len(parse_sections(self._path.read_text(encoding='utf-8')))


logger.debug(f'checked {document.name} ({sections_checked} sections)')
```

3. **Dunders keep the meaning the language gives them**
   `len()` is expected to be cheap and non-destructive; `==` is expected to mean identity.

```python
# ❌ Bad — `__len__` drains the stream to answer, so the `if` below consumes every finding
# and the loop that follows writes nothing: an empty report for a run that found plenty.
# And `__eq__` compares only the document name, so the same rule name in two corpora
# collapses into one entry when the report builder puts them in a set, and one corpus's
# findings silently disappear.
class FindingStream:
    def __len__(self) -> int:
        return sum(1 for _ in self._checks)


class RuleRef:
    def __eq__(self, other: object) -> bool:
        return isinstance(other, RuleRef) and self.name == other.name


if len(findings):
    for finding in findings:
        report.write_finding(finding)
```

```python
# ✅ Good — the stream advertises that it is one-shot and offers no length; identity covers
# every field that distinguishes one reference from another, with a matching hash.
class FindingStream:
    """A single-pass stream of findings. Iterating it consumes it."""

    def __iter__(self) -> Iterator[Finding]:
        return self

    def __next__(self) -> Finding:
        return next(self._checks)


@dataclass(frozen=True)
class RuleRef:
    corpus: str
    name: str


for finding in findings:
    report.write_finding(finding)
```

4. **Separate the lookup from the effect**
   Only one of "which checker handles this document type" and "run it" writes anything.

```python
# ❌ Bad — a name that reads like a query, a body that writes. The maintainer who filtered
# the document list with this to see which types had a checker configured emptied every
# pending finding buffer into the report in the process, halfway through the run.
def checker_for(document_type: str) -> Checker | None:
    checker = CHECKERS.get(document_type)
    if checker is None:
        return None
    checker.flush_findings()  # hidden effect
    return checker
```

```python
# ✅ Good — the lookup is pure; the effect says what it does in its name and reports what
# it did.
def checker_for(document_type: str) -> Checker | None:
    """Return the checker configured for ``document_type``, or None if there is none."""
    return CHECKERS.get(document_type)


def flush_findings(document_type: str) -> int:
    """Write the checker's buffered findings to the report.

    Args:
        document_type: Frontmatter ``type`` value the checker is registered under.

    Returns:
        Findings written by the flush; zero if no checker is configured.

    Raises:
        ReportError: If the report rejects the write.
    """
    checker = checker_for(document_type)
    if checker is None:
        return 0
    return checker.flush_findings()
```

## Why It Matters

Every broken convention forces a reader to open the implementation, and across a package that cost is paid
mostly in bugs. Python charges more for it than most languages: nothing in the syntax distinguishes an
attribute read from a file read, a cheap `len()` from a directory walk, or a pure call from one that writes, so
the name and the shape are the *only* signal a caller has. There is no type to consult and no compiler to
object.

Consistency also compounds. Because every resource-owning class here is built by `connect` and torn down by
`disconnect`, a plain `Type(...)` tells a reviewer the instance owns no handle — or that something is wrong.
That inference is available only while the vocabulary holds everywhere; one class that spells it `close` costs
every reader the habit.

## Pragmatism Caveat

A domain term beats a convention when it is genuinely clearer. `render` on a report template beats `to_rendered`
because render is the established verb in that domain. Prefer the domain word only when it is *more*
predictable, not merely more clever.

Some deviations are imposed from outside. A context manager must spell its methods `__enter__` and `__exit__`,
and a third-party base class dictates its own method names — so match the foreign convention at the boundary
and the package convention everywhere else. A class that is both connectable and a context manager wraps
`connect`/`disconnect`; it does not rename them.

When you deviate deliberately — a lookup that memoises, a method named for a dependency's vocabulary — say why
in a docstring at the declaration. An undocumented deviation is always wrong; the next reader cannot tell it
from a mistake.

## Checklist

Before committing code, verify:

- [ ] A name predicts what the call costs: anything that opens a file, walks a directory, or blocks says so
- [ ] `__init__` performs no I/O; anything that must open something first is built by a `connect` classmethod
- [ ] Lifecycle is spelled `connect`/`disconnect`, and `disconnect` is safe to call twice or without connecting
- [ ] Paired operations reuse the package's existing verb pair rather than a synonym
- [ ] No property performs I/O, blocks, or mutates; parses and reads are methods named for what they do
- [ ] `__len__` is cheap and non-destructive, `__iter__` does not surprise on a second pass, and `__eq__` and
      `__hash__` agree on the same fields
- [ ] More than two or three related parameters are a dataclass or settings object; no positional `bool`
- [ ] No function named for a query performs an effect; lookup and effect are separate functions
- [ ] Any intentional deviation is documented in a docstring at the declaration

## References

- [principle-single-responsibility](principle-single-responsibility.md) - Related: A class that cannot be named
  in one sentence cannot have a predictable API

## External References

- [PEP 8 — Style Guide for Python Code](https://peps.python.org/pep-0008/)
- [PEP 20 — The Zen of Python](https://peps.python.org/pep-0020/)
- [Principle of Least Surprise (principles-wiki.net)](https://principles-wiki.net/principles:principle_of_least_surprise)
- [The Principle of Least Astonishment](https://dev.to/notmattlucas/the-principle-of-least-astonishment-3f9k)
- [What is the Principle of Least Astonishment?](https://softwareengineering.stackexchange.com/a/187462)
