---
name: "python-errors-handling"
description: "Catching exceptions: narrowest clause first, `except Exception` only at a declared degrade boundary, binding with `as exc`, logging via `logger.exception`, and documenting a degraded return. Load when writing an except clause, adding a degrade path, or reviewing a broad catch"
type: "core"
scope: "global"
---

# Exception Handling

A handler is a claim that this code knows what to do about this failure. The claim is checked by asking two
questions of every `except`: what exactly does it catch, and what does it do — because a handler that catches
broadly and does nothing is indistinguishable from a bug, and it hides every future failure that lands in the
same block.

**`except Exception` is allowed here, and is never silent.** A blanket ban would be wrong for this project: a
status check must report a corpus as unloadable rather than propagating a YAML parser's undocumented
exception; a best-effort cleanup must not mask the original failure; a parallel fan-out across checkers must
not let one checker's surprise kill the whole report. What is forbidden is a broad catch that neither logs nor
re-raises, and one that binds nothing so the exception is unreachable even for a log line.

Chaining with `raise ... from exc` is owned by ruff `B904` and is not restated as a rule below. Declaring
exception classes is owned by [python-exceptions](python-exceptions.md); log formatting beyond §5 is owned by
[logging](logging.md).

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

## 2. `except Exception` Requires a Declared Degrade Boundary

A broad catch is written only where the operation's contract is "this must not propagate", and the handler says
so in a comment or in the enclosing function's docstring. Three shapes qualify:

| Boundary | Why broad is right |
|----------|--------------------|
| Status check | The point is to report whether a corpus loads, including the states a YAML or JSON Schema parser raises in undocumented ways |
| Best-effort cleanup in `finally` or `close` | A failure discarding a half-written report must not replace the failure that caused the teardown |
| Parallel fan-out over independent units | One document's surprise must not abort the other ninety, and the result carries the per-unit outcome |

Outside these, a broad catch is a narrow catch that was not looked up.

```python
# ❌ Bad — a broad catch in the middle of the check path. A malformed section outline is
# now reported as "no findings" and the run completes with the document marked clean
def check_document(self, path: Path) -> list[Finding]:
    try:
        return self._run_checks(path)
    except Exception as exc:
        logger.error(f'Check failed for {path}: {exc}')
        return []
```

```python
# ✅ Good — a declared degrade boundary; the docstring is part of the contract
def check_corpus_status(self) -> dict[str, Any]:
    """Report whether the corpus and its specification can be loaded.

    Never raises: any failure reaching this method is reported as an unloadable status
    so a calling report receives an answer rather than an exception.

    Returns:
        Mapping with ``loadable`` and, when unloadable, ``error`` describing the failure.
    """
    try:
        self._load_spec()
    except Exception as exc:  # degrade boundary: status must answer, never raise
        logger.exception(f'Corpus status check failed for {self.corpus_name}')
        return {'loadable': False, 'error': str(exc)}
    return {'loadable': True}
```

Ruff's `BLE001` (blind-except) is **not recommended** for this repository. It cannot see a degrade boundary, so
it would fire on every sanctioned site above and force a `noqa` on each — which converts a reviewed decision
into visual noise and trains readers to skip the suppression that matters. The review question in §4 is the
check; a linter that cannot ask it is not a substitute.

## 3. A Handler Binds Its Exception

Every `except` clause binds with `as exc`. A bare `except SomeError:` with no binding does not appear.

Without the binding the exception object does not exist in the handler, so nothing can log it, inspect its
attributes, attach it to a chained raise, or put it in a degraded result. The handler is structurally incapable
of doing anything informative with the failure it just caught — the information was there and was discarded at
the clause.

The name is `exc`, not `e`: a single letter says nothing, and in a handler long enough to need scrolling the
reader has to find the clause again to learn what it holds.

```python
# ❌ Bad — the exception is gone. The log line says a document's frontmatter failed and
# nothing more, so a YAML syntax error, a missing `name` field, and a `type` outside the
# schema's enum are one indistinguishable entry in the report
try:
    self._parse_frontmatter(path)
except FrontmatterError:
    logger.warning(f'Could not parse frontmatter in {path}')
```

```python
# ✅ Good — bound, so the cause reaches both the log and the caller
try:
    self._parse_frontmatter(path)
except FrontmatterError as exc:
    logger.warning(f'Could not parse frontmatter in {path}: field={exc.field}')
    raise DocumentLoadError(path) from exc
```

## 4. A Handler Logs or Re-Raises — Never Neither

Every handler does at least one of: log the failure, or re-raise (as-is, or wrapped in a domain exception).
A handler that does neither is the violation this document exists to name.

A reviewer classifies each `except` block into one of four behaviours:

| Behaviour | Verdict |
|-----------|---------|
| Logs and continues | **Sanctioned** at a degrade boundary (§2), with the degraded result documented (§6) |
| Logs and re-raises as a domain error | **Sanctioned** — the wrapping layer records context the caller's traceback would lack |
| Re-raises without logging | **Acceptable** when the caller logs; say which layer that is, in a comment or the docstring |
| Neither logs nor re-raises | **The violation** — the failure left no trace and no signal |

The fourth case is worse than an unhandled exception. An unhandled failure is loud and gets fixed; a swallowed
one turns a corpus full of broken documents into a clean-looking report, and the defect is found weeks later
when an agent follows a rule document that was never actually checked.

```python
# ❌ Bad — a skipped document leaves the report short and the caller is told the corpus
# passed. The corpus has a gap and nothing in the logs points at this line
for path in corpus_paths:
    try:
        self._check_document(path)
    except FrontmatterError:
        pass
```

```python
# ✅ Good — logs and continues, at a fan-out boundary where the per-unit outcome is
# reported back
findings: dict[str, list[Finding]] = {}
for checker in self._checkers:
    try:
        findings[checker.name] = checker.check(document)
    except Exception as exc:  # degrade boundary: one checker must not abort the fan-out
        logger.exception(f'Checker {checker.name} failed on {document.path}')
        findings[checker.name] = []
        failures[checker.name] = str(exc)
```

```python
# ✅ Good — re-raises without logging, and names the layer that does log
try:
    self._parse_frontmatter(path)
except FrontmatterError as exc:
    # The corpus runner logs every DocumentLoadError with the path and corpus name;
    # logging here would duplicate that line for every document.
    raise DocumentLoadError(path) from exc
```

`pass` inside an `except` is the shape to look for in a diff. The rare legitimate one — a cleanup that is
genuinely fine to skip — still logs at debug level, which is not `pass`.

**Enforcement:** ruff `S110`/`S112` — not currently enabled; see the checklist.

## 5. Log With `logger.exception`, Not an f-String of `str(exc)`

Inside an `except` block, a failure is logged with `logger.exception(...)`. `logger.error(f'... {exc}')` is
not used there.

`logger.exception` attaches the traceback and the chained `__cause__`; `str(exc)` is one sentence from the
outermost exception. The difference is the whole diagnosis: with the traceback an operator sees which call
raised and what it was wrapping, and without it they see "invalid frontmatter" and no indication of which
document, which checker, or what the underlying parser said.

The f-string itself stays — this project interpolates its log messages, and the context in the message is what
makes the traceback findable. What changes is the method, and that the message carries context rather than a
repeat of the exception's own text.

```python
# ❌ Bad — the traceback is discarded. "Check run failed: invalid frontmatter" is every
# operator's entire information, and the chained schema error naming the offending field
# is not in the log at all
except SpecLoadError as exc:
    logger.error(f'Check run failed: {exc}')
    raise
```

```python
# ✅ Good — traceback and cause chain preserved, message carries the identifying context
except SpecLoadError as exc:
    logger.exception(f'Check run failed for {path} against spec {spec_name}')
    raise
```

Outside an `except` block `logger.exception` has no traceback to attach and is wrong; use `logger.error` there.
Levels, logger construction, and message style are owned by [logging](logging.md).

**Enforcement:** ruff `TRY400` — not currently enabled; see the checklist.

## 6. A Degraded Return Value Is Part of the Documented Contract

Where a handler returns a degraded value instead of raising — a status mapping with `loadable: False`, a
per-unit result map with failures recorded, an empty finding list on a skipped document — that value and the
conditions producing it are documented in the function's `Returns:` section.

Returning a degraded value **is** handling, and a legitimate third option beside log-and-continue and re-raise.
What makes it legitimate is the documentation: an undocumented degraded return is a lie about the function's
success, because the caller has no way to know that the value it received means "this did not work". Documented,
it is a contract the caller can branch on.

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
    except Exception as exc:  # degrade boundary
        logger.exception(f'Check failed for {path}')
        return 0
```

```python
# ✅ Good — the degraded outcome is in the contract and is distinguishable from success
def check_document(self, path: Path) -> DocumentReport:
    """Check a document against its corpus specification.

    Never raises for a checker failure: the outcome is reported in the report so a corpus
    run can decide whether to continue or stop.

    Returns:
        A report whose ``findings`` holds what the checkers reported on success, and whose
        ``error`` is set and ``findings`` is empty when a checker could not run against the
        document.
    """
    try:
        return DocumentReport(findings=self._run_checks(path))
    except Exception as exc:  # degrade boundary: the run decides, this layer reports
        logger.exception(f'Check failed for {path}')
        return DocumentReport(findings=[], error=str(exc))
```

A degraded value that is indistinguishable from a legitimate result — `0` findings, an empty list, `None` —
needs a richer return type rather than a docstring note, because no caller reliably reads the note.

## Checklist

Before committing code, verify:

- [ ] Every `except` clause names the narrowest classes the block actually handles, and the `try` wraps only
      the statements that can raise them
- [ ] Every `except Exception` sits at a status check, a best-effort cleanup, or a parallel fan-out, and the
      boundary is stated in a comment or the function docstring
- [ ] Every `except` clause binds its exception as `exc`
- [ ] No handler in the diff both fails to log and fails to re-raise; no `except` body is a bare `pass`
- [ ] Every re-raise-without-logging handler names the layer that does the logging
- [ ] Every log call inside an `except` block uses `logger.exception`, with a message carrying identifying
      context rather than repeating `str(exc)`
- [ ] Every degraded return value is described in the function's `Returns:`, and is distinguishable from a
      legitimate success value

## References

- [python-exceptions](python-exceptions.md) - Related: Declaring the exception classes these
  handlers catch and wrap
- [logging](logging.md) - Related: Logger construction, levels, and message style for the calls in §5
- [principle-least-surprise](principle-least-surprise.md) - Foundation: Why a swallowed failure that returns a
  success-shaped value is the costliest defect here
- [python-dataclasses](python-dataclasses.md) - Related: The result record a documented degraded return needs

## External References

- [logging.Logger.exception - Python Standard Library](https://docs.python.org/3/library/logging.html#logging.Logger.exception)
- [Ruff - flake8-blind-except (`BLE`)](https://docs.astral.sh/ruff/rules/#flake8-blind-except-ble)
