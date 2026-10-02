---
name: "error-types"
description: "Declaring error variants: each derives from `Error`, each way to fail is a class, each belongs to one operation, the union of lower variants sits on a required keyword-only `source`, messages are built from fields and never from the source, and names follow the failure. Load when defining an error class or union, choosing what it carries or what it is called, or deciding which operation raises it"
type: "core"
scope: "global"
---

# Error Types

**An error's contract lives in its types, so the checker enforces it rather than a reviewer.** Every cause
stays reachable, typed, and stated once. Classes serve the runtime, since they are what `raise` and `except`
take. A union of them, written on the `source` that wraps them, serves the checker. A variant's typed `source`
links it to the failure beneath it, so the errors of every layer form one chain, each link naming only its own
step. Where a rule below could be left to review or made a type, it is a type, and this is what that buys:

| Mistake | Caught by |
|---|---|
| A variant added to a union and not handled | ty, at the `assert_never` arm of every `match` over it |
| A variant raised in a handler without its cause | ty, a missing argument for the required `source` |
| A cause of the wrong kind passed as `source` | ty, at the constructor call |
| A union written in an `except` clause | ty, `invalid-exception-caught` |
| A field read that not every variant of a union has | ty, at the attribute access |
| A raise in a handler without `from` | ruff `B904` |
| A `source` pointing to a higher layer | import-linter, since the annotation is an import |

This document owns how a variant is declared. Catching and raising in a handler are owned by
[error-handling](error-handling.md); a defect's built-in, a framework's seam, a foreign failure's translation and
a layer's wrap are owned by [error-boundaries](error-boundaries.md).

## 1. Every Expected Failure Derives From `Error`

A failure a caller is expected to report derives directly from the package's shared `Error` base, and from
nothing else: input that cannot be read, a specification that does not parse, an argument outside every corpus.
`Error` is the boundary the command line catches to report a failure and exit with its status. A domain error
outside it escapes as a traceback, and one deriving from a built-in is caught by every handler written for that
built-in. A defect in the code raises a built-in instead ([error-boundaries](error-boundaries.md)).

No variant derives from another variant. A subclass is caught by its parent's `except` clause. Two failures a
caller must tell apart then collapse into one handler, and the order of the clauses becomes load-bearing. What
groups variants is a union ([§4](#4-the-ways-an-operation-fails-are-a-union-written-on-the-source-that-wraps-them)),
not a base class.

```python
# ❌ Bad — a decode failure is a kind of read failure, so the handler for unreadable files also took every
# non-UTF-8 specification, and the check reported each one as a permission problem
class SpecDecodeError(SpecReadError):
    """A specification file's bytes are not UTF-8."""
```

```python
# ✅ Good — siblings, each caught only where it is named
class SpecDecodeError(Error):
    """A specification file's bytes are not UTF-8."""
```

## 2. Each Way to Fail Is a Class of Its Own

A variant stands for one way to fail — one step that could not be done, or one rule the input breaks — and its
name says which. A variant raised for two hides which one failed: a reader of the message, and a handler
branching on the class, both see one failure where there were two.

Each way to fail is a class even when several share their fields and their recovery. A class is what `except`
names and what a `match` arm checks, so ty sees the new one a handler misses. A reason enum on one class hides the
ways from both: a handler tests the field, and a reason added later takes whatever branch is left. The one enum a
variant may carry classifies a foreign failure's facts, where the set comes from outside the package
([error-boundaries](error-boundaries.md)).

```python
# ❌ Bad — one class and a reason enum, so a handler that skipped duplicates and stopped on everything else
# tested `exc.problem`, and a reason added later was skipped as if it were a duplicate
class OutlineEntryError(Error):
    def __init__(self, entry: str, problem: OutlineEntryProblem) -> None: ...
```

```python
# ✅ Good — a class per way to fail, each caught or matched by name
class EmptyOutlineEntryError(Error):
    def __init__(self, line: LineNumber) -> None: ...


class DuplicateOutlineEntryError(Error):
    def __init__(self, entry: str, line: LineNumber) -> None: ...
```

## 3. A Variant Belongs to One Operation

Only the operation a variant belongs to raises it: directly, or from the private helpers that carry out its
steps. Another function that fails the same way declares its own variant, or lets this one pass through from
beneath ([error-boundaries](error-boundaries.md)), and never raises it itself. A variant shared by two calls
hides which one failed from a caller holding both, as surely as one class covering two steps does.

An abstract method is one operation. Its variants are the union of what its implementations can raise, and a
caller holding the interface handles all of them. Each implementation's `Raises:` lists only what that
implementation raises; a variant it cannot raise is left out, never listed as "Never". Every variant in a
`source` union can come out of the call it wraps: a member nothing raises makes every exhaustive handler carry a
case that cannot happen.

```python
# ❌ Bad — two readers raise one class, so the loader that calls both reported a failed outline read as a
# failed specification read
def read_spec(path: Path) -> str: ...     # raises SpecReadError
def read_outline(path: Path) -> str: ...  # raises SpecReadError too
```

```python
# ✅ Good — each operation raises its own variant
def read_spec(path: Path) -> str: ...     # raises SpecReadError
def read_outline(path: Path) -> str: ...  # raises OutlineReadError
```

## 4. The Ways an Operation Fails Are a Union, Written on the `source` That Wraps Them

A variant that wraps an operation failing more than one way annotates its `source` with the union of those
variants, written out in place: the closed set lives where it is used. An operation with one way to fail is
wrapped by that one class. A union used in more than one place — the `source` of two variants, a parameter, a
helper that matches on it — is named once with a `type` statement, declared after the variants in the module
[python-modules](python-modules.md) places them in, under a comment naming the operation, since a `type`
statement carries no docstring. A union used once stays inline: a name read in one place is only a second place
to look. How an alias is spelled is owned by [python-typing](python-typing.md).

A base class is open: a subclass declared anywhere joins it, so no checker can say that a handler covers every
case. A union is closed. Annotated on a `source` field or a parameter, it lets ty prove that a `match` over it
is exhaustive. The union is never raised and never caught, because `except` takes classes and tuples, not
unions. A field every variant carries is declared on each variant, and reading it through the union
type-checks because every member has it.

```python
# ❌ Bad — an open family: a subclass added in another module joined it, and every handler written for
# "every way fetch_spec fails" stopped covering them without a warning
class FetchSpecError(Error):
    """Reading a specification failed."""
```

```python
# ✅ Good — the closed set written where it is used, or named once when three variants share it
class SchemaLoadError(Error):
    def __init__(self, schema: str, *, source: SpecReadError | SpecDecodeError) -> None: ...


# Every way `fetch_spec` fails.
type FetchSpecError = SpecReadError | SpecDecodeError
```

## 5. Each Variant Builds Its Own Message From Its Fields

A variant's constructor takes as parameters the context it reports, and the failure it wraps as `source`
([§6](#6-a-wrapped-failure-is-a-typed-keyword-only-source)). It stores each one as an attribute, builds the
message once, and passes it to `super().__init__`. Each variant words its own message and never inherits a
sibling's. The raise site passes values, never text. A message composed at the raise site reads differently at
every site and hides its values in prose. A handler reads the attributes and never parses `str(exc)`. Only
context safe to show in a log or a traceback becomes an attribute or message text, never a credential, a
token, or a credential-bearing URL.

```python
# ❌ Bad — the text is composed at the raise site, so a handler that needed the path had to parse it back
raise SpecDecodeError(f'{path} is not UTF-8')
```

```python
# ✅ Good — values in, one message out, every value readable as an attribute
class SpecDecodeError(Error):
    """A specification file's bytes are not UTF-8.

    Attributes:
        path: The specification file.
        source: The decoder's failure, which locates the first byte that does not decode.
    """

    path: Path
    source: UnicodeDecodeError

    def __init__(self, path: Path, *, source: UnicodeDecodeError) -> None:
        self.path = path
        self.source = source
        super().__init__(f'specification {path} is not UTF-8')
        self.__cause__ = source
```

## 6. A Wrapped Failure Is a Typed, Keyword-Only `source`

A variant that stands for a lower failure takes it as a keyword-only `source` parameter, after the context,
annotated with its exact type: a lower variant, a lower operation's union, or the foreign exception it
translates ([error-boundaries](error-boundaries.md)). The constructor stores it as `source` and assigns it to
`__cause__`. The raise site then reads `SpecReadError(path, source=exc) from exc`: the typed field and the chain
side by side, and a context parameter added later never takes `source`'s place.

The annotation is the contract. A handler reads `exc.source` as that type, and a `match` over it is checked for
exhaustiveness. Assigning `__cause__` makes the chain part of the class rather than of each raise site, and a
traceback and `logger.exception` walk that chain. A `source` is never annotated `Exception`, `BaseException` or
`object`, which would erase the one fact a handler branches on. The annotation is an import, so a source always
comes from the variant's own layer or one beneath it, and the import-linter contract forbids a chain that points
upward.

```python
# ❌ Bad — the source type is erased, so the handler that reports a decode failure as a finding probed with
# isinstance, and a new failure beneath it passed every probe unnoticed
def __init__(self, corpus: str, source: Exception) -> None: ...
```

```python
# ✅ Good — the source is every way the call beneath fails, and the variant adds the corpus it was loading
class OutlineLoadError(Error):
    """A corpus's outline specification could not be loaded.

    Attributes:
        corpus: The corpus whose outline was being loaded.
        source: The read, decode or syntax failure of the outline file.
    """

    corpus: str
    source: SpecReadError | SpecDecodeError | OutlineSyntaxError

    def __init__(self, corpus: str, *, source: SpecReadError | SpecDecodeError | OutlineSyntaxError) -> None:
        self.corpus = corpus
        self.source = source
        super().__init__(f'cannot load the outline of corpus {corpus}')
        self.__cause__ = source
```

## 7. A Variant Takes a `source` Exactly When It Is Raised in a Handler

A variant raised inside an `except` clause declares `source` as a required parameter: no default, never
annotated `| None`. A variant raised anywhere else, from this layer's own check, declares no `source` at all.
A foreign cause counts: an `OSError` caught from a read is the `source` of the variant raised in its place. A
caught exception becomes a `source` only when it carries something the variant does not already hold; one that
is only noise is not caught at all ([error-handling](error-handling.md)).

An optional `source` makes one class stand for two failures, one with a cause beneath it and one without. A
handler cannot tell which it holds without testing for `None`, and the chain is complete for one and missing
for the other. A class raised both ways is two variants. A required `source` also turns a forgotten cause into
a type error at the raise site, where an optional one lets it pass.

```python
# ❌ Bad — one class for a refused read and for an empty file, so a handler that retried the refused read
# retried the empty file too, and `source` was None exactly where the retry needed it
class SpecReadError(Error):
    def __init__(self, path: Path, *, source: OSError | None = None) -> None: ...
```

```python
# ✅ Good — raised in a handler, so source is required; raised from a check, so there is none
class SpecReadError(Error):
    def __init__(self, path: Path, *, source: OSError) -> None: ...


class EmptySpecError(Error):
    def __init__(self, path: Path) -> None: ...
```

## 8. A Message States Its Own Step, Never Its Source's

A message names the step that failed and the context the variant holds for itself, and nothing of its source.
It does not interpolate the source, and does not copy the source's fields or attributes to rebuild its sentence,
whether the source is an `Error` or foreign: an `OSError`, a `UnicodeDecodeError`, a parser's exception.

The cause is read where it lives. A handler reads the variant's own typed fields, and `exc.source` as its
declared type. Whatever reports the failure walks the chain from `__cause__`, one message per link. A message
that embeds its source repeats the same reason once per layer, and one that paraphrases a source's attributes
turns typed values back into prose a handler would have to parse.

```python
# ❌ Bad — the cause is copied into the text, so every report of an unreadable outline carried the operating
# system's reason once per layer, and a handler that needed the reason parsed it back out of a sentence
super().__init__(f'cannot read specification {path}: {source.strerror}')
super().__init__(f'cannot load the outline of corpus {corpus}: {source}')
```

```python
# ✅ Good — each message names its own step; the reason is a typed field, or the next link of the chain
super().__init__(f'cannot read specification {path}')
super().__init__(f'cannot load the outline of corpus {corpus}')
```

## 9. Every Variant Documents What Failed and When

A variant's docstring opens with one line saying what failed, says when the variant is raised if the class name
does not, and lists every field under `Attributes:`, `source` included. A handler reads a variant through its
fields alone, so each is contract: `source`'s annotation names a type, not which lower step it stands for. The
`Raises:` section of the function that reaches it is owned by [python-docstrings](python-docstrings.md).

## 10. A Name Says What Failed, and a Verb Starts Only a Union's

Every name ends in `Error`, and its form says what kind of thing it names:

| Names | Form | Examples |
|---|---|---|
| A step that could not be done | `<Subject><Step>Error` | `SpecReadError`, `DirListError`, `OutlineLoadError` |
| A rule the input breaks | `<Condition><Subject>Error` | `EmptyCorpusNameError`, `UnknownSpecFileTypeError` |
| A named union | `<Operation>Error`, the function's name in `PascalCase` | `FetchSpecError` for `fetch_spec` |

A name that begins with a verb is always a union, so it never appears in an `except`. A method's union puts the
method's name before its class's, so `CorpusName.parse` gives `ParseCorpusNameError`. The name at a `source`
annotation then says which call produced the failure. Case is owned by [python-naming](python-naming.md).

## Checklist

Before committing code, verify:

- [ ] Every domain error derives directly from `Error`; no variant derives from another
- [ ] Each way to fail is a class of its own; no variant tells the package's own failures apart with an enum
- [ ] Each variant is raised only by its operation or that operation's private helpers; an implementation's
      `Raises:` lists only what it raises, with no "Never" entries
- [ ] A `source` wrapping several variants is annotated with their union, named by a `type` alias only when
      used in more than one place; every variant in it can occur
- [ ] Each variant's `__init__` takes values, stores them and builds its own message; no raise site passes
      message text, and nothing holds a credential or a token
- [ ] A wrapped failure is a keyword-only `source` of its exact type, stored and assigned to `__cause__`;
      never `Exception`, `BaseException` or `object`
- [ ] Every class raised inside a handler requires `source`, every other class declares none, and no `source`
      has a default or `| None`
- [ ] No message interpolates its source or rebuilds a sentence from its fields, foreign or not
- [ ] Every variant's docstring says what failed and lists every field, `source` included, under `Attributes:`
- [ ] A failed step is named `<Subject><Step>Error`, a broken rule `<Condition><Subject>Error`, and only a
      named union starts with a verb

## References

- [error-handling](error-handling.md) - Related: Owns catching a union's variants and the raise that wraps a
  failure
- [error-boundaries](error-boundaries.md) - Related: Owns a defect's built-in, a framework's seam, a foreign
  failure's translation and a layer's wrap
- [python-fn](python-fn.md) - Related: Owns keyword-only parameters, which `source` is
- [python-typing](python-typing.md) - Related: Owns the spelling of a union and of a `type` alias, and the
  `match` over one
- [python-modules](python-modules.md) - Related: Owns where an error type is declared in its module
- [python-docstrings](python-docstrings.md) - Related: Owns the `Attributes:` section a variant fills and
  the `Raises:` section that lists the variants a call reaches
- [python-naming](python-naming.md) - Related: Owns the case of a class name
- [principle-least-surprise](principle-least-surprise.md) - Foundation: An error type should predict what a
  caller can catch

## External References

- [Python documentation — Exception context](https://docs.python.org/3/library/exceptions.html#exception-context)
- [PEP 695 — Type Parameter Syntax](https://peps.python.org/pep-0695/)
- [Python tutorial — User-defined Exceptions](https://docs.python.org/3/tutorial/errors.html#user-defined-exceptions)
