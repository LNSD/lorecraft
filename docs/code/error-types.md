---
name: "error-types"
description: "Declaring error types: variants deriving from `Error`, the union of lower variants on each `source`, named only when reused, a required keyword-only `source` on every variant raised in a handler, messages built from fields, and when a layer wraps. Load when defining an error class or union, choosing what it carries, or wrapping a lower failure"
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

Catching a union, the raise that wraps a failure, and dispatching on a union are owned by
[error-handling](error-handling.md). This document owns how a domain error is declared, and
what a broken contract raises instead.

## 1. Every Expected Failure Derives From `Error`

A failure a caller is expected to report derives directly from the package's shared `Error` base, and from
nothing else: input that cannot be read, a specification that does not parse, an argument outside every corpus.
`Error` is the boundary the command line catches to report a failure and exit with its status. A domain error
outside it escapes as a traceback, and one deriving from a built-in is caught by every handler written for that
built-in.

No variant derives from another variant. A subclass is caught by its parent's `except` clause. Two failures a
caller must tell apart then collapse into one handler, and the order of the clauses becomes load-bearing. What
groups variants is a union ([§3](#3-an-operation-that-fails-more-than-one-way-declares-a-type-union)), not a
base class.

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

## 2. A Broken Contract Raises a Built-in, Never an `Error`

A function whose caller broke its contract, such as a heading level outside 1 to 6 or a check registered twice,
raises a built-in: `ValueError` for a value the parameter does not allow, `TypeError` for an unsupported type,
`RuntimeError` for an operation the object's state forbids. The test is who fixes it. A change to the code is a
defect and raises a built-in; a change to the files a command read is an `Error`. The command line turns an
`Error` into a message and an exit status, which is right for a malformed specification and wrong for a bug: a
defect raised as an `Error` is reported as the user's fault, with no traceback to locate the call.

The test is where the value came from, not where the check sits. A `__post_init__` guard that `parse` shares
checks input, so it raises an `Error` ([pattern-value-object](pattern-value-object.md)); the same guard on a
value only code supplies raises a built-in.

A defect a test must single out subclasses the one built-in it already is, never `BaseException` and never two
built-ins, and builds its message from its attributes as a variant does. `NotImplementedError` marks only a
base-class operation a subclass has not provided, and `abc.abstractmethod` is preferred, so a missing method
fails when the class is instantiated rather than when it is first called.

```python
# ❌ Bad — two modules registering one check name is a bug in the package, but as an Error it was printed
# as a problem with the user's repository, exited 2, and no traceback pointed at the second registration
def register_check(check: Check) -> None:
    if check.name in _CHECKS:
        raise CheckNameTakenError(check.name)
```

```python
# ✅ Good — the defect propagates as a RuntimeError, with the traceback that locates it
def register_check(check: Check) -> None:
    if check.name in _CHECKS:
        raise RuntimeError(f'check {check.name!r} is registered twice')
```

## 3. The Ways an Operation Fails Are a Union, Written on the `source` That Wraps Them

Each way an operation fails is one variant class. A variant that wraps an operation failing more than one way
annotates its `source` with the union of those variants, written out in place: the closed set lives where it is
used. An operation with one way to fail is wrapped by that one class. A union used in more than one place — the
`source` of two variants, a parameter, a helper that matches on it — is named once with a `type` statement,
declared after the variants in the module [python-modules](python-modules.md) places them in, under a comment
naming the operation, since a `type` statement carries no docstring. A union used once stays inline: a name
read in one place is only a second place to look. How an alias is spelled is owned by
[python-typing](python-typing.md).

A base class is open: a subclass declared anywhere joins it, so no checker can say that a handler covers every
case. A union is closed. Annotated on a `source` field ([§6](#6-a-wrapped-failure-is-a-typed-keyword-only-source))
or a parameter, it lets `ty` prove that a `match` over it is exhaustive, and flag the match that misses a
variant, through a union nested in another as well. The union is never raised and never caught, because
`except` takes classes and tuples, not unions. A field every variant carries is declared on each variant, and
reading it through the union type-checks because every member has it.

```python
# ❌ Bad — an open family: a subclass added in another module joined it, and every handler written for
# "every way fetch_spec fails" stopped covering them without a warning
class FetchSpecError(Error):
    """Reading a specification failed."""
```

```python
# ✅ Good — the variants, and the closed set they form, written where it is used
class SpecReadError(Error):
    """The operating system refused to read a specification file."""


class SpecDecodeError(Error):
    """A specification file's bytes are not UTF-8."""


class SchemaLoadError(Error):
    def __init__(self, schema: str, *, source: SpecReadError | SpecDecodeError) -> None: ...
```

```python
# ✅ Good — the same set is the source of three variants, so it is named once
# Every way `fetch_spec` fails.
type FetchSpecError = SpecReadError | SpecDecodeError
```

## 4. One Variant per Failure Step

A variant stands for one step that can fail, and its name says which step. A variant raised from two steps
hides which one failed: a reader of the message, and a handler branching on the class, both see one failure
where there were two. Different messages alone do not make different steps. Different recoveries, or different
context to carry, do. Every variant in a `source` union can come out of the call it wraps, raised there or
passed through from beneath. A member nothing raises makes every exhaustive handler carry a case that cannot happen.

```python
# ❌ Bad — raised for the listing and for each read, so a handler that reports an unreadable file as a
# finding had to treat an unlistable directory the same way
class SpecStorageError(Error):
    """Specification storage failed."""
```

```python
# ✅ Good — the class names the step
class SpecListError(Error):
    """The specification directory cannot be listed."""


class SpecReadError(Error):
    """The operating system refused to read a specification file."""
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
translates. The constructor stores it as `source` and assigns it to `__cause__`. The raise site then reads
`SpecReadError(path, source=exc) from exc`: the typed field and the chain side by side, and a context parameter
added later never takes `source`'s place.

The annotation is the contract. A handler reads `exc.source` as that type, and a `match` over it is checked for
exhaustiveness. Assigning `__cause__` makes the chain part of the class rather than of each raise site, and a
traceback and `logger.exception` walk that chain. A `source` is never annotated `Exception`, `BaseException` or
`object`, which would erase the one fact a handler branches on.

The annotation is an import, so a source always comes from the variant's own layer or one beneath it. The
import-linter contract that forbids a lower layer from importing a higher one therefore forbids a chain that
points upward.

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
A foreign cause counts: a `ValueError` caught from an enum lookup is the `source` of the variant raised in its
place.

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

The cause is read where it lives. A handler reads `exc.source` as its declared type, so `exc.source.strerror` is
a typed value rather than words in a sentence. Whatever reports the failure walks the chain from `__cause__`, one
message per link. A message that embeds its source repeats the same reason once per layer, and one that
paraphrases a source's attributes turns typed values back into prose a handler would have to parse.

```python
# ❌ Bad — the cause is copied into the text, so every report of an unreadable outline carried the operating
# system's reason once per layer, and a handler that needed the reason parsed it back out of a sentence
super().__init__(f'cannot read specification {path}: {source.strerror}')
super().__init__(f'cannot load the outline of corpus {corpus}: {source}')
```

```python
# ✅ Good — each message names its own step; the reason is `exc.source.strerror`, or the next link of the chain
super().__init__(f'cannot read specification {path}')
super().__init__(f'cannot load the outline of corpus {corpus}')
```

## 9. Wrap Only Where the Layer Adds a Step or an Identity

A function wraps a lower failure in a variant of its own when it adds something the lower error cannot know:
the step it was taking, or the identity of what it was working on. When it adds neither, the lower variants
propagate unchanged, and the function's `Raises:` lists them beside its own. A wrapper that only renames the
failure is a new class that carries no new fact, and a caller who could have matched the lower variants now has
to unwrap first.

```python
# ❌ Bad — the wrapper knows nothing the source does not, so a handler written for SpecDecodeError stopped
# seeing it
super().__init__('cannot fetch specification')
```

```python
# ✅ Good — this layer's own failure is new, and the read failures pass through unwrapped
def parse_outline(path: Path) -> Outline:
    """Parse an outline specification file.

    Raises:
        SpecReadError: The operating system refused to read the file.
        SpecDecodeError: The file's bytes are not UTF-8.
        OutlineSyntaxError: The file is not a valid outline.
    """
```

## 10. Every Variant Documents What Failed and When

A variant's docstring opens with one line saying what failed, says when the variant is raised if the class name
does not, and lists every field under `Attributes:`, `source` included. A handler reads a variant through its
fields alone, so each is contract: `source`'s annotation names a type, not which lower step it stands for. The
`Raises:` section of the function that reaches it is owned by [python-docstrings](python-docstrings.md).

## 11. A Variant Is Named for Its Failure, a Union for Its Operation

A variant's name says what failed and ends in `Error`: `SpecDecodeError`, `EmptyCorpusNameError`. A named
union is named for the operation whose failures it enumerates: the function's name in `PascalCase` with `Error`
added, so `fetch_spec` gives `FetchSpecError`. A method's name comes before its class's, so `CorpusName.parse` gives
`ParseCorpusNameError`. The name at a `source` annotation then says which call produced the failure. Case is
owned by [python-naming](python-naming.md).

## 12. The Layers Form One Chain

Put together, each layer contributes one link, carrying its own facts. The raise sites are owned by
[error-handling](error-handling.md).

```python
# Layer 1, `fetch_spec`: the foreign failure enters the package's errors as a typed source
except OSError as exc:
    raise SpecReadError(path, source=exc) from exc

# Layer 2, `parse_outline`: no identity to add, so fetch_spec's variants pass through
# unwrapped; only its own step, the syntax, is a new variant
raise OutlineSyntaxError(path, line)

# Layer 3, `load_outline`: the corpus is what this layer knows and the lower ones do not
except (SpecReadError, SpecDecodeError, OutlineSyntaxError) as exc:
    raise OutlineLoadError(corpus, source=exc) from exc
```

The chain an unreadable outline leaves: each message names one step, and the reason is a typed value at the
bottom, reached through `.source` or by walking `__cause__`:

```text
OutlineLoadError   corpus='code'   "cannot load the outline of corpus code"
└─ .source: SpecReadError   path=docs/__meta__/code.json   "cannot read specification docs/__meta__/code.json"
   └─ .source: PermissionError   strerror='Permission denied'
```

## Checklist

Before committing code, verify:

- [ ] Every domain error derives directly from `Error`; no variant derives from another
- [ ] A broken contract raises a built-in, never an `Error`; a subclass of one has one built-in base, and
      `NotImplementedError` marks only an operation a subclass must provide
- [ ] A `source` wrapping several variants is annotated with their union, named by a `type` alias only when
      used in more than one place
- [ ] Each variant stands for one failure step, and every variant in a `source` union can occur
- [ ] Each variant's `__init__` takes values, stores them and builds its own message; no raise site passes
      message text, and nothing holds a credential or a token
- [ ] A wrapped failure is a keyword-only `source` of its exact type, stored and assigned to `__cause__`;
      never `Exception`, `BaseException` or `object`
- [ ] Every class raised inside a handler requires `source`, every other class declares none, and no `source`
      has a default or `| None`
- [ ] No message interpolates its source or rebuilds a sentence from its fields, foreign or not
- [ ] A variant exists only where its layer adds a step or an identity; otherwise the lower variants pass through
- [ ] Every variant's docstring says what failed and lists every field, `source` included, under `Attributes:`
- [ ] A variant is named for its failure and a named union for its operation, both ending in `Error`

## References

- [error-handling](error-handling.md) - Related: Owns catching a union's variants, the raise that wraps a
  failure, and dispatching on a union
- [python-fn](python-fn.md) - Related: Owns keyword-only parameters, which `source` is
- [python-typing](python-typing.md) - Related: Owns the spelling of a union and of a `type` alias
- [python-modules](python-modules.md) - Related: Owns where an error type is declared in its module
- [python-docstrings](python-docstrings.md) - Related: Owns the `Attributes:` section a variant fills and
  the `Raises:` section that lists the variants a call reaches
- [python-naming](python-naming.md) - Related: Owns the case of a class name
- [principle-least-surprise](principle-least-surprise.md) - Foundation: An error type should predict what a
  caller can catch

## External References

- [Python documentation — Built-in Exceptions](https://docs.python.org/3/library/exceptions.html)
- [Python documentation — Exception context](https://docs.python.org/3/library/exceptions.html#exception-context)
- [PEP 695 — Type Parameter Syntax](https://peps.python.org/pep-0695/)
- [Python tutorial — User-defined Exceptions](https://docs.python.org/3/tutorial/errors.html#user-defined-exceptions)