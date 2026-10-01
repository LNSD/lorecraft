---
name: "error-handling"
description: "Catching and consuming errors: the narrowest clause, a union caught by its variants, `source=exc` with `from exc` on every raise in a handler, noise tested rather than caught, one clause per wrapped variant, `except Exception` only at a declared degrade boundary, binding as `exc`, the command line's report-and-exit, and documenting a degraded return or a parse outcome. Load when writing an except clause, raising inside one, adding a degrade path, reporting a failure at the command line, or reviewing a broad catch"
type: "core"
scope: "global"
---

# Error Handling

A handler is a claim that this code knows what to do about this failure. The claim is checked by asking two
questions of every `except`: what exactly does it catch, and what does it do — because a handler that catches
broadly and does nothing is indistinguishable from a bug, and it hides every future failure that lands in the
same block.

**A failure travels up as a chain, and is logged, or reported to the user, once, where it is handled.** A layer
that cannot handle a failure wraps it in its own variant, with the caught error as `source`, and raises; the
layer that decides what the failure means logs it with `logger.exception`, which walks the whole chain, and at
the command line's top level that layer is the user. `except Exception` is allowed, at a declared degrade
boundary, and is never silent.

Declaring error classes, their unions and their `source` is owned by [error-types](error-types.md), and where an
error crosses a boundary by [error-boundaries](error-boundaries.md). Branching on a union with `match` is owned
by [python-typing](python-typing.md). How a caught exception is logged is owned by [logging](logging.md).

## 1. Catch the Narrowest Exception You Can Name

An `except` clause names the specific classes this block knows how to handle. Where several are handled
differently, they are separate clauses, most specific first.

A wide clause catches failures the author never considered, which is the same as handling them wrongly. It also
catches the ones a future edit introduces — a new call inside the `try` starts raising something unrelated and
lands in a handler written for a different problem, at which point the symptom is a misleading log line rather
than a traceback.

```python
# ❌ Bad — the retry was written for a document an editor replaces mid-read, but it also
# catches the malformed frontmatter and the unreadable-permissions rejection, so a
# document that will never parse is read five times with backoff before failing, on
# every corpus run
try:
    self._read_document(path)
except Exception:
    self._retry_read(path)
```

```python
# ✅ Good — the clause names what is actually retryable; anything else propagates with
# its own traceback
try:
    self._read_document(path)
except (FileNotFoundError, BlockingIOError):
    self._retry_read(path)
```

The `try` block is kept to the statements that can raise what is being caught. A five-line `try` around one
risky call means four other lines whose failures silently take the handler's path.

## 2. Catch a Union by Its Variants

An `except` clause names classes, so a union is caught by listing its variants: in one tuple when the handler
treats them alike, in a clause each when it does not ([§4](#4-each-wrapped-variant-gets-its-own-clause)). A type
checker narrows `exc` to the union of the classes listed.

A union in an `except` clause is a `TypeError`, and a late one, whether it is a `type` alias or written out as
`A | B`. Python evaluates the clause only when an exception reaches it, so the first real failure is replaced by
a complaint about the handler written for it. ty reports the clause as `invalid-exception-caught`; a test that
stays on the success path never does.

```python
# ❌ Bad — every test that loads an outline passes; the first unreadable file raises a TypeError from the
# except clause instead of the read failure it was written for
try:
    text = fetch_spec(path)
except SpecReadError | SpecDecodeError as exc:
    raise OutlineLoadError(corpus, source=exc) from exc
```

```python
# ✅ Good — the variants, listed; the checker sees `exc` as `SpecReadError | SpecDecodeError`
try:
    text = fetch_spec(path)
except (SpecReadError, SpecDecodeError) as exc:
    raise OutlineLoadError(corpus, source=exc) from exc
```

## 3. A Raise in a Handler Passes `source=exc` and `from exc`, Never `from None`

A variant raised inside an `except` clause stands for the failure it caught, so it takes that failure twice:
as `source=exc`, the typed field [error-types](error-types.md) requires, and in `from exc`, which ruff `B904`
requires of every raise in a handler. Both name the same `exc`. `from exc` alone chains an exception the
variant does not declare, so no handler can read it as a typed value.

`from None` is never written. It runs after the constructor and sets `__cause__` back to `None`, so `source`
says there is a cause while the chain every traceback and `logger.exception` reads says there is none, and the
lower failure's reason disappears from every report. The usual reason to write it is that the caught exception
is noise, a `KeyError` from a lookup. Then the code is not a handler: it tests the condition, and the variant is
raised outside any `except`, with no `source`. For an enum, the test is membership:
`if name not in Dialect: raise UnknownDialectError(name)`, where catching the `ValueError` of `Dialect(name)`
would hold nothing the variant does not.

```python
# ❌ Bad — the KeyError was noise, so the author hid it, and the pattern spread to handlers whose cause mattered
try:
    return self._corpora[name]
except KeyError:
    raise UnknownCorpusError(name) from None
```

```python
# ✅ Good — no handler: a lookup that finds nothing is not a failure to keep
corpus = self._corpora.get(name)
if corpus is None:
    raise UnknownCorpusError(name)
return corpus
```

## 4. Each Wrapped Variant Gets Its Own Clause

A layer that wraps each variant of a lower union in a variant of its own gives each its own `except` clause,
raising its own variant with the caught error as `source`, and `from exc`
([§3](#3-a-raise-in-a-handler-passes-sourceexc-and-from-exc-never-from-none)).

The clause is where the mapping is visible: one lower failure in, one upper failure out, readable without opening
either class. Sibling variants make clause order carry no meaning. Where one caught class subclasses another, as
`FileNotFoundError` does `OSError`, the subclass comes first ([§1](#1-catch-the-narrowest-exception-you-can-name)).
Code that later branches on which variant a `source` holds uses `match`, closed by `assert_never`
([python-typing-unreachable](python-typing-unreachable.md)), never an `isinstance` chain.

```python
# ✅ Good — one lower failure in, one upper failure out, per clause
try:
    text = fetch_spec(path)
except SpecDecodeError as exc:
    raise OutlineDecodeError(corpus, source=exc) from exc
except SpecReadError as exc:
    raise OutlineReadError(corpus, source=exc) from exc
```

## 5. `except Exception` Requires a Declared Degrade Boundary

A broad catch is written only where the operation's contract is "this must not propagate", and the handler says
so in a comment or in the enclosing function's docstring. Three shapes qualify:

| Boundary | Why broad is right |
|----------|--------------------|
| Status check | The point is to report whether a corpus loads, including the states a YAML or JSON Schema parser raises in undocumented ways |
| Best-effort cleanup in `finally` or `close` | A failure discarding a half-written report must not replace the failure that caused the teardown |
| The call for one unit of a parallel fan-out | One document's surprise must not abort the other ninety, and the result carries the per-unit outcome |

Outside these, a broad catch is a narrow catch that was not looked up. This section governs only how broad a
catch is: a narrow `except` needs no boundary, even when it degrades
([§7](#7-a-handler-raises-recovers-degrades-or-reports--never-nothing)).

```python
# ❌ Bad — a broad catch in the middle of the check path. An outline that fails to load is now an
# outline with no sections, and every document of the corpus passes the structure check
def outline_sections(self, corpus: str) -> list[str]:
    try:
        return self._load_outline(corpus).sections
    except Exception:
        logger.exception('outline failed', extra={'fields': {'corpus': corpus}})
        return []
```

```python
# ✅ Good — a declared degrade boundary; the docstring is part of the contract
def check_corpus_status(self) -> CorpusStatus:
    """Report whether the corpus and its specification can be loaded.

    Never raises: any failure reaching this method is reported as an unloadable status
    so a calling report receives an answer rather than an exception.

    Returns:
        A status whose `failure` is set when the corpus cannot be loaded.
    """
    try:
        self._load_spec()
    except Exception as exc:  # degrade boundary: status must answer, never raise
        logger.exception('corpus status check failed', extra={'fields': {'corpus': self.corpus_name}})
        return CorpusStatus(loadable=False, failure=exc)
    return CorpusStatus(loadable=True)
```

Ruff's `BLE001` (blind-except) is not enabled: it cannot see a degrade boundary, so it would force a `noqa` on
every sanctioned site above. The review question in
[§7](#7-a-handler-raises-recovers-degrades-or-reports--never-nothing) is the check.

## 6. A Handler That Raises or Keeps Its Exception Binds It as `exc`

A handler that raises a variant, or keeps the failure in a degraded result, binds the caught exception with
`as exc`: it is the `source` the variant requires and the value the result carries. A handler that only logs
with `logger.exception`, cleans up and re-raises with a bare `raise`, or recovers, binds nothing. The active
exception reaches `logger.exception` and `raise` without a name, and ruff's `F841` reports a binding nothing
reads.

The name is `exc`, not `e` or `error`: a single letter says nothing, and one name everywhere means a reader
never has to find the clause again to learn what it holds.

```python
# ❌ Bad — unbound, so there is nothing to pass as source; ty reports the missing argument, and a
# `from exc` added by hand would chain a cause the variant does not declare
try:
    outline = parse_outline(path)
except OutlineSyntaxError:
    raise OutlineLoadError(corpus)
```

```python
# ✅ Good — bound, so the cause reaches the caller as the new error's source
try:
    outline = parse_outline(path)
except OutlineSyntaxError as exc:
    raise OutlineLoadError(corpus, source=exc) from exc
```

## 7. A Handler Raises, Recovers, Degrades or Reports — Never Nothing

A reviewer classifies each `except` block:

| Behaviour | Verdict |
|-----------|---------|
| Wraps in a variant and raises ([§3](#3-a-raise-in-a-handler-passes-sourceexc-and-from-exc-never-from-none)) | **The default.** No log: the layer that handles the failure logs it once, with the chain |
| Cleans up and re-raises with a bare `raise` | **Sanctioned** |
| Recovers: retries, or takes another path, for the classes it names ([§1](#1-catch-the-narrowest-exception-you-can-name)) | **Sanctioned** |
| Degrades: returns the value its `Returns:` documents ([§8](#8-a-degraded-return-value-is-part-of-the-documented-contract)) | **Sanctioned** for a narrow catch, and for a broad one at a degrade boundary ([§5](#5-except-exception-requires-a-declared-degrade-boundary)). It logs only when the value drops the failure; a value that carries it on is reported by its reader |
| Reports and exits: catches `Error`, writes the failure and its chain to stderr, and exits through the framework's exception | **Sanctioned** only at the command line's top level, where the user is the handler — the one place `except Error` is written |
| Logs and re-raises | **Not used** — every layer that does it logs the same failure again |
| Does none of these | **The violation** — the failure left no trace and no signal |

The last case is worse than an unhandled exception. An unhandled failure is loud and gets fixed; a swallowed
one turns a corpus full of broken documents into a clean-looking report, and the defect is found weeks later
when an agent follows a rule document that was never actually checked.

```python
# ❌ Bad — a skipped document leaves the report short and the caller is told the corpus
# passed. The corpus has a gap and nothing in the logs points at this line
for path in corpus_paths:
    try:
        self._check_document(path)
    except OutlineSyntaxError:
        pass
```

`pass` inside an `except` is the shape to look for in a diff. The rare legitimate one — a cleanup that is
genuinely fine to skip — still logs at debug level, which is not `pass`.

## 8. A Degraded Return Value Is Part of the Documented Contract

Where a handler returns a degraded value instead of raising — a status with `loadable` false, a per-unit result
map with failures recorded, an empty finding list on a skipped document — that value and the conditions
producing it are documented in the function's `Returns:` section. The value keeps the exception, not its
`str()`: an upper variant's message names only its own step, so the text alone drops the cause its chain carries.

Returning a degraded value **is** handling. What makes it legitimate is the documentation: an undocumented
degraded return is a lie about the function's success, because the caller has no way to know that the value it
received means "this did not work". Documented, it is a contract the caller can branch on.

```python
# ❌ Bad — the return type and docstring promise a finding count. A caller summing these
# across a corpus reports a clean run of zero findings and never learns a checker crashed
def check_document(self, path: Path) -> int:
    """Check a document.

    Returns:
        Number of findings reported.
    """
    try:
        return len(self._run_checks(path))
    except Exception:  # degrade boundary
        logger.exception('check failed', extra={'fields': {'document': str(path)}})
        return 0
```

```python
# ✅ Good — the degraded outcome is in the contract and is distinguishable from success
def check_document(self, path: Path) -> DocumentOutcome:
    """Check a document against its corpus specification.

    Never raises for a checker failure: the outcome is reported so a corpus run can
    decide whether to continue or stop.

    Returns:
        An outcome whose `findings` holds what the checkers reported on success, and
        whose `failure` holds the exception and `findings` is empty when a checker
        could not run against the document.
    """
    try:
        return DocumentOutcome(findings=self._run_checks(path))
    except Exception as exc:  # degrade boundary: one unit of the corpus fan-out
        logger.exception('check failed', extra={'fields': {'document': str(path)}})
        return DocumentOutcome(findings=[], failure=exc)
```

A degraded value that is indistinguishable from a legitimate result — `0` findings, an empty list, `None` —
needs a richer return type rather than a docstring note, because no caller reliably reads the note.

A parse outcome is not a degraded return. A value that says what is wrong with the input — a block that is not
valid YAML — is a result, one member of the parse's union, compared by value. It records the foreign error's
facts as typed fields read from its attributes, never the exception, which compares by identity, and never its
`str()`: `InvalidYamlBlock(problem=exc.problem, line=...)` rather than `InvalidYamlBlock(detail=str(exc))`.

## Checklist

Before committing code, verify:

- [ ] Every `except` clause names the narrowest classes the block handles, and the `try` wraps only the
      statements that can raise them
- [ ] No `except` clause names a union, as an alias or as `A | B`; a union is caught by listing its variants
- [ ] Every variant raised inside a handler is raised as `Variant(..., source=exc) from exc`; no `from None`
- [ ] No exception that is only noise is caught; its condition is tested instead
- [ ] A layer that maps each lower variant to its own gives each an `except` clause of its own
- [ ] Every `except Exception` sits at a status check, a best-effort cleanup, or one unit of a parallel fan-out,
      and the boundary is stated in a comment or the function docstring
- [ ] Every handler that raises a variant or keeps the failure binds it as `exc`
- [ ] Every handler wraps and raises, re-raises after cleanup, recovers, degrades, or reports and exits at the
      command line's top level; none logs and re-raises, and no `except` body is a bare `pass`
- [ ] Every degraded return is described in the function's `Returns:`, keeps the exception rather than its
      `str()` or logs it, and is distinguishable from a legitimate success value
- [ ] A parse outcome records the foreign error's facts as typed fields, never the exception or its `str()`

## References

- [error-types](error-types.md) - Related: Owns the error classes, unions and typed sources these handlers
  catch, match on and raise
- [error-boundaries](error-boundaries.md) - Related: Owns the framework exception a command handler exits
  through, and the variant a foreign exception is translated into
- [python-typing-unreachable](python-typing-unreachable.md) - Related: Owns the `match` closed by `assert_never` that branches on a
  caught variant's `source`
- [logging](logging.md) - Related: Owns how a handler logs, including `logger.exception` and its fields
- [principle-least-surprise](principle-least-surprise.md) - Foundation: Why a swallowed failure that returns a
  success-shaped value is the costliest defect here
- [python-dataclasses](python-dataclasses.md) - Related: The result record a documented degraded return needs

## External References

- [Ruff - flake8-blind-except (`BLE`)](https://docs.astral.sh/ruff/rules/#flake8-blind-except-ble)
- [Ruff - `raise-without-from-inside-except` (`B904`)](https://docs.astral.sh/ruff/rules/raise-without-from-inside-except/)
- [Ruff - `unused-variable` (`F841`)](https://docs.astral.sh/ruff/rules/unused-variable/)
