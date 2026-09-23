---
name: "python-exceptions"
description: "Exception selection and inheritance: choosing a built-in category, defining domain hierarchies, avoiding BaseException and multiple inheritance, and carrying structured context. Load when raising a new failure, defining an exception class, or choosing its base class"
type: "core"
scope: "global"
---

# Exception Types and Inheritance

An exception's base class tells callers what kind of failure they are catching. Use an existing built-in
exception when its documented meaning is the whole contract; introduce a domain exception when callers need a
stable, domain-specific recovery boundary.

How exceptions are caught, logged, and chained is owned by
[python-errors-handling](python-errors-handling.md). This document owns which exception type is raised and
what it inherits from.

## 1. Choose the Base Class by Catching Semantics

Choose the narrowest established category whose meaning matches the failure. The test is at the call site:
would a caller that catches this base class reasonably intend to catch this failure too?

| Base | Use when |
|------|----------|
| `Exception` | A domain failure has no more specific built-in meaning |
| `ValueError` | An argument has the right kind of value but violates a required value constraint |
| `TypeError` | An operation receives an unsupported type; Python does not already raise it naturally |
| `KeyError` | A required key is absent from a mapping-like interface |
| `IndexError` | A sequence-like interface is addressed outside its valid range |
| `RuntimeError` | The operation is invalid in the object's current runtime state and no narrower category fits |
| `OSError` or a subclass | The failure comes from the operating system, filesystem, or a system-level resource |
| `ImportError` | An import fails, including a requested name missing from a module |
| `ModuleNotFoundError` | A specific module cannot be located |
| `NotImplementedError` | A base-class operation requires an implementation from a subclass |
| `ExceptionGroup` | Several independent `Exception` instances must be reported together |

Do not translate one built-in into another merely to standardize spelling. Preserve `FileNotFoundError`,
`UnicodeDecodeError`, `TimeoutError`, and other precise built-ins unless a domain boundary needs to add a
stable meaning that callers actually select.

```python
# ❌ Bad — the generic type discards the argument category that callers already understand
if max_words < 1:
    raise Exception('max words must be positive')
```

```python
# ✅ Good — callers may handle this alongside other invalid argument values
if max_words < 1:
    raise ValueError(f'max_words must be positive, got {max_words}')
```

`NotImplementedError` is not a general-purpose "unsupported" error and is distinct from the `NotImplemented`
singleton used by binary special methods. Prefer `abc.abstractmethod` when a base method must always be
implemented. If an operation is deliberately unavailable for one implementation, raise a domain exception
such as `UnsupportedCorpusError` or omit that operation from its interface.

## 2. User-Defined Exceptions Inherit From One Exception Type

A user-defined exception inherits from `Exception` or from one meaningful subclass of `Exception`. It never
inherits directly from `BaseException`: that branch contains process-control exceptions such as
`KeyboardInterrupt`, `SystemExit`, and `GeneratorExit`, which ordinary `except Exception` handlers
intentionally do not intercept.

Use one exception base. Multiple inheritance between built-in exception types can conflict over constructor
arguments and CPython memory layout, and it gives the exception two competing catching meanings.

```python
# ❌ Bad — ordinary exception handlers will not catch this domain failure
class CheckerError(BaseException):
    pass


# ❌ Bad — two catch categories and potentially incompatible built-in layouts
class InvalidFrontmatterError(ValueError, RuntimeError):
    pass
```

```python
# ✅ Good — one base expresses the category callers should select
class InvalidFrontmatterError(ValueError):
    """Raised when a document's frontmatter contains an invalid value."""
```

Subclass a built-in only when inheriting its catching semantics is intentional. If callers catching every
`ValueError` should not catch the domain failure, derive the domain exception from the package's domain base
instead.

## 3. A Domain Hierarchy Follows Recovery Boundaries

Define a domain base when callers need to catch failures from a whole public operation or subsystem without
catching unrelated Python errors. Add a more specific subclass when callers have a distinct response to that
failure, not merely because a validator or parser supplied a different message or numeric code.

```python
# ❌ Bad — one class per validator code, although callers report all three identically
class FrontmatterCode1042Error(Exception):
    pass


class FrontmatterCode1043Error(Exception):
    pass


class FrontmatterCode1044Error(Exception):
    pass
```

```python
# ✅ Good — the hierarchy represents the choices available to callers
class CheckerError(Exception):
    """Base class for failures produced by a document check."""


class SchemaUnavailableError(CheckerError):
    """Raised when a corpus schema cannot be loaded, so no document in it can be checked."""


class DocumentUnreadableError(CheckerError):
    """Raised when one document cannot be read and the run may skip it."""
```

Keep a validator's error code as structured data on the relevant exception when it remains useful for
diagnostics. It does not automatically deserve another level in the class hierarchy.

## 4. Exceptions Carry the Context a Handler Needs

An exception stores stable values that a handler may inspect as attributes. Its constructor builds the human
message once and passes it to `super().__init__`. Callers inspect attributes rather than parsing `str(exc)`.

```python
# ❌ Bad — the handler must parse prose to recover the document name and the overrun
raise CheckerError(f'{excess_words} words over budget in {document_name}')
```

```python
# ✅ Good — structured context for code and one message for people
class BudgetExceededError(CheckerError):
    """Raised when a document's prose exceeds its length budget."""

    def __init__(self, document_name: str, excess_words: int) -> None:
        self.document_name = document_name
        self.excess_words = excess_words
        super().__init__(f'{document_name} exceeds its prose budget by {excess_words} words')
```

Store only context safe to expose through logs and tracebacks. Credentials, tokens, and credential-bearing
URLs never become exception attributes or message text.

## 5. Preserve Foreign Exceptions Until a Domain Boundary Adds Meaning

Do not wrap an exception merely because it came from a dependency. Let it propagate when its existing type is
already part of the function's contract. Translate it at a public boundary when the dependency type is an
implementation detail or when the domain can add a recovery decision.

```python
# ❌ Bad — this translation loses the precise filesystem category and adds no domain meaning
try:
    return document_path.read_text(encoding='utf-8')
except OSError as exc:
    raise CheckerError(str(exc)) from exc
```

```python
# ✅ Good — the domain type states which operation failed and preserves the original cause
try:
    schema = json.loads(schema_text)
except json.JSONDecodeError as exc:
    raise SchemaUnavailableError(corpus_name) from exc
```

The translated exception carries safe domain context; the chained cause retains the dependency traceback.

## Checklist

Before committing code, verify:

- [ ] A built-in exception is used when its documented category fully describes the failure
- [ ] A custom exception's single base matches the category callers should intentionally catch
- [ ] No user-defined exception inherits directly from `BaseException`
- [ ] No exception class uses multiple inheritance
- [ ] `NotImplementedError` is used only for a subclass operation that still requires implementation
- [ ] A domain base represents a public recovery boundary, and subclasses represent distinct caller responses
- [ ] Validator codes are structured attributes where useful, not automatically distinct exception classes
- [ ] Stable handler inputs are attributes; no caller must parse `str(exc)`
- [ ] Exception attributes and messages contain no secrets or credential-bearing URLs
- [ ] A translated dependency exception adds domain meaning and preserves its cause

## References

- [python-errors-handling](python-errors-handling.md) - Related: Owns catching, chaining, logging, and recovery
- [python-naming](python-naming.md) - Related: Owns exception class naming
- [python-docstrings](python-docstrings.md) - Related: Owns documentation of caller-visible exceptions
- [python-modules](python-modules.md) - Related: Owns module placement and package exports
- [principle-least-surprise](principle-least-surprise.md) - Foundation: A type should predict what callers can catch

## External References

- [Python documentation — Built-in Exceptions](https://docs.python.org/3.12/library/exceptions.html)
- [Python tutorial — User-defined Exceptions](https://docs.python.org/3.12/tutorial/errors.html#user-defined-exceptions)
