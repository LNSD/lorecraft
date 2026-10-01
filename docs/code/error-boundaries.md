---
name: "error-boundaries"
description: "Where the package's errors meet what surrounds them: a code defect raises a built-in, a framework's exception is raised only at its seam, a foreign failure is translated into a variant with typed facts and its source, and a layer wraps only where it adds a step or an identity. Load when choosing between an `Error` and a built-in, raising inside a pydantic validator or a Typer callback, catching an exception from the standard library or a dependency, or wrapping a lower layer's failure"
type: "core"
scope: "global"
---

# Error Boundaries

**A variant is the package's own vocabulary, and a boundary is where something else turns into one, or one turns
into something else.** Four boundaries meet the package's errors: a defect in the code, which is not the user's
failure and is no variant; a framework, which accepts only its own exceptions; a foreign library or the
operating system, whose exceptions enter as the source of a variant; and a lower layer, whose variants pass
through or are wrapped. Each is crossed in one place, in one direction.

How a variant is declared is owned by [error-types](error-types.md). How a raise inside a handler is written is
owned by [error-handling](error-handling.md).

## 1. A Broken Contract Raises a Built-in, Never an `Error`

A function whose caller broke its contract, such as a check registered twice, raises a built-in: `ValueError`
for a value the parameter does not allow, `TypeError` for an unsupported type, `RuntimeError` for an operation
the object's state forbids, and `NotImplementedError` for an operation a subclass must provide. The list is
closed. A `KeyError` in particular is not raised for a broken contract: every handler written around a mapping
lookup catches it by accident, and its name says nothing about a caller's mistake.

The test is who fixes it. A change to the code is a defect and raises a built-in; a change to the files a
command read is an `Error`. The command line turns an `Error` into a message and an exit status, which is right
for a malformed specification and wrong for a bug: a defect raised as an `Error` is reported as the user's fault,
with no traceback to locate the call.

A value object's invariant always raises its variant, whoever constructs the value
([pattern-value-object](pattern-value-object.md)). A value object cannot know whether its caller parsed input or
joined a literal, so the built-in rule covers a contract a function states about its parameters, and never a
type's invariant.

A defect a test must single out subclasses the one built-in it already is, never `BaseException` and never two
built-ins, and builds its message from its attributes as a variant does. `abc.abstractmethod` is preferred to
`NotImplementedError`, so a missing method fails when the class is instantiated rather than when it is called.

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

## 2. A Framework's Exception Is Raised Only at Its Seam

Some exceptions are a framework's protocol rather than the package's errors: pydantic turns only its own
`PydanticCustomError`, or a validator's `ValueError`, into a validation error, and Typer renders a usage error or
an exit status only from `typer.BadParameter` or `typer.Exit`. Such an exception is raised only at the seam
where the framework demands it — the hook pydantic calls, the command handler Typer runs — and nowhere else.

It is not a variant, so the rules for variants do not bind it, and its message may carry the caught variant's
text, since that text is all the framework shows. Beneath the seam the code raises and catches variants as
usual, and the seam translates at the last step. A framework exception raised deeper ties the library to the
framework, and a caller outside it catches an exception it never asked for.

```python
# ❌ Bad — the parser raises Typer's exception, so the library imports the command line's framework, and a
# check calling the parser outside any command received a usage error
def parse_section_name(raw: str) -> SectionName:
    if not raw:
        raise typer.BadParameter('section name cannot be empty')
```

```python
# ✅ Good — the pydantic hook is the seam; the parse beneath it raises variants, and only the last step
# speaks pydantic's language
@classmethod
def _from_pydantic(cls, value: str) -> Self:
    try:
        return cls.parse(value)
    except (EmptySectionNameError, InvalidSectionNameCharacterError) as exc:
        raise PydanticCustomError('section_name', '{reason}', {'reason': str(exc)}) from exc
```

## 3. A Foreign Failure Is Translated Into Typed Facts, Keeping Its Source

The variant that catches a foreign exception — the operating system's, the standard library's, a dependency's —
is where that failure enters the package. It keeps the exception as its `source`, so the chain, the traceback and
`logger.exception` still show where the call failed. It also takes the facts its callers act on as typed fields
of its own, read from the exception's attributes at the raise site. Nothing above that variant reads the foreign
exception: a handler branches on the variant's fields, which the package owns and the checker knows.

This is the one place an enum field belongs on a variant. The set of reasons comes from outside the package — the
kinds of refusal an `errno` can report — and an enum classifies them into cases a `match` covers exhaustively. The
package's own ways to fail are classes ([error-types](error-types.md)).

```python
# ❌ Bad — the handler reads the foreign exception, so it branches on a bare int, and an errno it did not
# think of fell through to the retry
except SpecReadError as exc:
    if exc.source.errno == errno.ENOENT:
        ...
```

```python
# ✅ Good — the translating variant classifies the refusal once; every handler above matches the enum
class ReadRefusal(Enum):
    """Why the operating system refused a read, classified from its `errno`."""

    NOT_FOUND = auto()
    PERMISSION_DENIED = auto()
    NOT_A_FILE = auto()
    OTHER = auto()


except OSError as exc:
    raise SpecReadError(path, ReadRefusal.from_error(exc), source=exc) from exc
```

## 4. Wrap Only Where the Layer Adds a Step or an Identity

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

## 5. The Layers Form One Chain

Put together, each layer contributes one link, carrying its own facts: the foreign failure enters with its
facts classified, a layer with nothing to add lets the variants through, and a layer that knows what it was
working on wraps with that identity.

```python
# Layer 1, `fetch_spec`: the foreign failure enters as a typed source, its refusal classified
except OSError as exc:
    raise SpecReadError(path, ReadRefusal.from_error(exc), source=exc) from exc

# Layer 2, `parse_outline`: no identity to add, so fetch_spec's variants pass through
# unwrapped; only its own step, the syntax, is a new variant
raise OutlineSyntaxError(path, line)

# Layer 3, `load_outline`: the corpus is what this layer knows and the lower ones do not
except (SpecReadError, SpecDecodeError, OutlineSyntaxError) as exc:
    raise OutlineLoadError(corpus, source=exc) from exc
```

The chain an unreadable outline leaves: each message names one step, each fact is a typed field, and the
foreign exception sits at the bottom, reached through `.source` or by walking `__cause__`:

```text
OutlineLoadError   corpus='code'   "cannot load the outline of corpus code"
└─ .source: SpecReadError   path=docs/__meta__/code.json   refusal=PERMISSION_DENIED   "cannot read specification docs/__meta__/code.json"
   └─ .source: PermissionError   errno=13   strerror='Permission denied'
```

## Checklist

Before committing code, verify:

- [ ] A broken contract raises `ValueError`, `TypeError`, `RuntimeError`, or `NotImplementedError` for an
      operation a subclass must provide; never an `Error`, a `KeyError` or another built-in
- [ ] A value object's invariant raises its variant, whoever constructs the value
- [ ] A defect's subclass has one built-in base and builds its message from its attributes
- [ ] A framework's exception is raised only in the hook the framework calls, translating a caught variant as
      the last step
- [ ] A variant that catches a foreign exception keeps it as `source` and exposes the facts callers act on as
      typed fields; no code above that variant reads the foreign exception
- [ ] An enum field on a variant classifies a foreign failure's facts, and nothing else
- [ ] A variant exists only where its layer adds a step or an identity; otherwise the lower variants pass
      through, listed in `Raises:`

## References

- [error-types](error-types.md) - Related: Owns how a variant, its `source` and its message are declared
- [error-handling](error-handling.md) - Related: Owns the raise inside a handler that each boundary is
  crossed with
- [pattern-adapter](pattern-adapter.md) - Related: The seam where a library's failures are translated
- [pattern-value-object](pattern-value-object.md) - Related: The value whose invariant raises a variant
- [principle-validate-at-edge](principle-validate-at-edge.md) - Foundation: A boundary is crossed once, at the
  edge

## External References

- [Python documentation — Built-in Exceptions](https://docs.python.org/3/library/exceptions.html)
- [Python documentation — `errno`](https://docs.python.org/3/library/errno.html)
- [pydantic — Custom errors](https://docs.pydantic.dev/latest/concepts/validators/#raising-validation-errors)
- [Typer — Exit and abort](https://typer.tiangolo.com/tutorial/terminating/)
