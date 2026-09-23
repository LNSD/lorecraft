---
name: "pattern-resource-lifecycle"
description: "Resource lifecycle: acquisition and release are named, paired, idempotent, and exception-safe via the context manager protocol. Load when a type opens a corpus, a worker pool, a schema cache, or a report file, when writing connect/disconnect, or when a cleanup call sits outside a finally block"
type: "core"
scope: "global"
---

# Resource Lifecycle (Acquire, Use, Release)

## Rule

A type that acquires something the process cannot leak — a worker pool, an index holding a file handle per
document, a schema cache read from disk, a report file being streamed to — has two phases with two distinct
failure modes. **Acquisition** fails for configuration reasons: a corpus root that does not exist, a format
specification that cannot be read, a schema that does not parse. **Use** fails for runtime reasons: a document
whose frontmatter is malformed, a section outline the spec cannot describe, a write that fails mid-report. The
phases must be separable by the caller, and release must happen on both paths.

Express that separation with the **context manager protocol** plus an explicit **`connect` / `disconnect`**
pair. The pair names the phases and is callable directly where a `with` block does not fit; the protocol makes
the release automatic and exception-safe where it does. Both exist on every acquiring type — they are not
alternatives.

Six rules:

1. **Acquisition names what it acquires; release is its inverse.** `connect` and `disconnect`, not `setup` and
   `cleanup` or `start` and `close`. A reader who sees `connect` knows what failed and what to retry; a reader
   who sees `setup` has to open the method to find out what it built.
2. **Anything acquired in `__init__` must be released if construction then fails** — or must not be acquired in
   `__init__` at all. A constructor that starts a worker pool and then raises while validating its next
   argument leaks that pool: the object never exists, so no caller can close it and no `__exit__` will run.
   Prefer configuring in `__init__` and acquiring in `connect`.
3. **Every acquiring type exposes `__enter__` and `__exit__`, and `__exit__` releases even when the body
   raised.** `__exit__` runs on the exception path; that is the whole point of implementing it. It must not
   return a truthy value unless it deliberately suppresses the exception — and it should not.
4. **`try` / `finally`, never a trailing release that only the happy path reaches.** A `disconnect()` as the
   last statement of a function is not cleanup; it is cleanup conditional on nothing going wrong, which is
   exactly the case where cleanup matters.
5. **A lifecycle is one state, not several booleans.** `_connected`, `_closing`, and `_index is not None` drift
   apart and encode states that cannot happen. One enum-valued attribute has exactly the states the resource
   has, and no combination that cannot.
6. **Release is idempotent.** `disconnect` on an already-released resource returns without raising, because it
   will be called twice: once explicitly, once by `__exit__`, and possibly once more by an error handler.

## Examples

1. **Acquiring in `__init__`, and leaking it when construction fails**
   The worker pool is started before the rest of the arguments are validated, so a bad parallelism value leaks
   live threads that no caller can ever reach.

```python
# ❌ Bad — the pool is running and the exception escapes `__init__`, so the object is never
# bound, `__exit__` never runs, and the threads keep the interpreter alive after the check
# run should have exited. A test that constructs a session per case hangs the whole suite.
class CorpusSession:
    def __init__(self, root: Path, parallelism: int) -> None:
        self._workers = ThreadPoolExecutor(max_workers=parallelism)
        if parallelism <= 0:
            raise ValueError('parallelism must be positive')
        self._parallelism = parallelism
```

```python
# ✅ Good — `__init__` only validates and stores configuration; nothing is acquired until
# `connect`, so a construction failure has nothing to leak.
class CorpusSession:
    """Checks the rule documents of one corpus against its format specification."""

    def __init__(self, root: Path, parallelism: int) -> None:
        """Configure the session. Acquires nothing; call `connect` to open the corpus.

        Args:
            root: Directory holding the corpus documents.
            parallelism: Documents checked concurrently. Must be positive.

        Raises:
            ValueError: If `parallelism` is not positive.
        """
        if parallelism <= 0:
            raise ValueError('parallelism must be positive')
        self._root = root
        self._parallelism = parallelism
        self._state = SessionState.DISCONNECTED
        self._index: CorpusIndex | None = None
```

2. **A release that only the happy path reaches**
   The session is closed at the end of the function, so a document that fails to parse — the case the cleanup
   exists for — skips it.

```python
# ❌ Bad — a document with malformed frontmatter raised halfway through the corpus, so
# `disconnect` never ran. The open handles stayed until the process died, and the next run
# over a large corpus failed with `OSError: Too many open files` rather than naming the one
# document that was actually broken.
def check_corpus(session: CorpusSession, documents: Iterator[Path]) -> list[Finding]:
    session.connect()
    findings = []
    for document in documents:
        findings.extend(session.check(document))
    session.disconnect()
    return findings
```

```python
# ✅ Good — the `with` block releases on both paths, and the parse failure propagates to the
# caller with every handle already closed.
def check_corpus(session: CorpusSession, documents: Iterator[Path]) -> list[Finding]:
    """Check every document in the corpus, releasing the session on success or failure."""
    findings = []
    with session:
        for document in documents:
            findings.extend(session.check(document))
    return findings
```

```python
# 🔶 Acceptable — when the acquiring and releasing calls are genuinely far apart (a watcher
# that connects at startup and disconnects on shutdown signal), `try`/`finally` carries the
# same guarantee without a `with` block spanning the whole run loop.
def watch_corpus(session: CorpusSession, changes: Iterator[Path]) -> None:
    session.connect()
    try:
        for document in changes:
            report(session.check(document))
    finally:
        session.disconnect()
```

3. **The lifecycle as one state, and a release that survives being called twice**
   Two booleans encode four states when the resource has three, and a `disconnect` that assumes it has an index
   raises the second time it is called — from `__exit__`, masking the real exception.

```python
# ❌ Bad — `_connected` and `_closing` can disagree, and the second `disconnect` raises
# AttributeError from inside `__exit__`, replacing the frontmatter error the caller needed
# to see with a traceback about a missing attribute.
class CorpusSession:
    def disconnect(self) -> None:
        self._closing = True
        self._index.close()
        del self._index
        self._connected = False
```

```python
# ✅ Good — one state attribute with exactly the states that exist, and a release that is a
# no-op when there is nothing to release, so `__exit__` can never mask the real failure.
class SessionState(Enum):
    """Lifecycle of a corpus session."""

    DISCONNECTED = 'disconnected'
    CONNECTED = 'connected'
    FAILED = 'failed'


class CorpusSession:
    def connect(self) -> None:
        """Open the corpus index.

        Raises:
            CorpusConnectionError: If the corpus root is missing or cannot be read.
        """
        if self._state is SessionState.CONNECTED:
            return
        try:
            self._index = CorpusIndex(self._root)
        except OSError as exc:
            self._state = SessionState.FAILED
            raise CorpusConnectionError(f'could not open corpus at {self._root}') from exc
        self._state = SessionState.CONNECTED
        logger.info(f'connected session to corpus at {self._root}')

    def disconnect(self) -> None:
        """Close the corpus index. Safe to call when already disconnected."""
        if self._index is None:
            return
        self._index.close()
        self._index = None
        self._state = SessionState.DISCONNECTED
        logger.info(f'disconnected session from corpus at {self._root}')

    def __enter__(self) -> 'CorpusSession':
        self.connect()
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        # Returns None, so an exception raised in the body propagates after release.
        self.disconnect()
```

4. **Releasing what was already acquired when a later acquisition fails**
   A type that acquires two things must not leak the first when the second fails.

```python
# ❌ Bad — the worker pool is running when the schema fails to load. `connect` raises, the
# caller never gets an object in a connected state, and the worker threads keep the process
# alive after the check run should have exited.
def connect(self) -> None:
    self._workers = ThreadPoolExecutor(max_workers=self._parallelism)
    self._schema = load_schema(self._schema_path)
    self._state = SessionState.CONNECTED
```

```python
# ✅ Good — the partial acquisition is unwound on the failing path, so a failed `connect`
# leaves exactly the state a never-connected session has.
def connect(self) -> None:
    """Start the worker pool and load the frontmatter schema.

    Raises:
        CorpusConnectionError: If the schema cannot be loaded.
    """
    self._workers = ThreadPoolExecutor(max_workers=self._parallelism)
    try:
        self._schema = load_schema(self._schema_path)
    except SchemaError as exc:
        self._workers.shutdown(wait=False)
        self._workers = None
        self._state = SessionState.FAILED
        raise CorpusConnectionError(f'could not load schema at {self._schema_path}') from exc
    self._state = SessionState.CONNECTED
```

## Why It Matters

**Leaked resources fail somewhere else.** A handle that is not closed does not raise where it was opened; it
raises in the next run, as a file-descriptor-limit error that names neither the code that leaked it nor the
malformed document that caused the leak. The cost of the bug is paid entirely in debugging time by someone who
did not write it.

**Cleanup that only runs on success is cleanup that never runs when it matters.** The happy path does not need
the release urgently — the failing path does, and a trailing `disconnect()` is precisely the arrangement that
skips it. `finally` and `__exit__` are the only two constructions that hold.

**Separate phases give the caller separate recoveries.** A failure in `connect` is a configuration problem:
fix the corpus path, fix the schema, do not retry in a tight loop. A failure during use is a per-document
problem: record a finding, skip the document, continue the run. Collapsing both into one exception type from
one method forces every caller to guess which one happened.

**A non-idempotent release turns one failure into two.** `__exit__` runs while an exception is in flight. If
release raises there, the second exception replaces the first, and the traceback describes the cleanup rather
than the fault. An idempotent `disconnect` cannot do this.

**One state attribute cannot disagree with itself.** Two booleans describe four combinations for a resource
that has three states, and the fourth is reachable by any early return that updates one and not the other.

## Pragmatism Caveat

This pattern is for types that acquire something the process must give back. Applying it elsewhere adds two
methods and a protocol to objects that hold nothing:

- **A pure transformation acquires nothing.** A frontmatter parser, a heading-outline extractor, a
  length-budget counter that reads its input and returns findings needs no lifecycle, no `connect`, and no
  context manager. Do not add them so that everything in a package "looks the same".
- **A short-lived handle borrowed from something else is released by its owner.** A file object taken from an
  open corpus index inside one function is closed there; it does not need its own context-manager type layered
  on top of the index.
- **A resource with no meaningful acquisition failure needs no separate `connect`.** If acquiring cannot fail
  in a way distinct from using — an in-memory document buffer, a temporary directory for a rendered report —
  one context manager is clearer than a `connect` / `disconnect` pair that can only succeed.
- **Do not wrap a third-party object that is already a context manager** merely to rename its methods. Use it
  directly inside your own `connect`.

Deviating is legitimate when one of these cases applies and the reason is written at the spot. **An
undocumented deviation is always wrong** — a release call outside a `finally`, or an acquiring type with no
`__exit__`, is indistinguishable from an oversight, and review must treat it as one.

## Checklist

- [ ] Acquisition is named for what it acquires (`connect`), and release is its inverse (`disconnect`)
- [ ] `__init__` acquires nothing, or releases what it acquired if it then raises
- [ ] The type implements `__enter__` and `__exit__`, and `__exit__` releases on the exception path
- [ ] `__exit__` returns `None` — it does not silently suppress the body's exception
- [ ] Every direct `connect` outside a `with` block is paired with a `disconnect` in a `finally`
- [ ] `disconnect` on an already-released resource returns without raising
- [ ] The lifecycle is one state attribute, not a set of booleans that can disagree
- [ ] A `connect` that acquires more than one thing unwinds the earlier acquisitions when a later one fails
- [ ] Acquisition failures raise a domain exception chained with `raise ... from exc`, distinct from use failures
- [ ] No lifecycle methods were added to a type that acquires nothing

## References

- [principle-least-surprise](principle-least-surprise.md) - Foundation: A caller expects `with` to release on the failing path
- [pattern-value-object](pattern-value-object.md) - Related: The lifecycle state is a value, not a pile of flags
- [pattern-registry](pattern-registry.md) - Related: Registered checkers are constructed by callers who then own their lifecycle

## External References

- [Python docs — With Statement Context Managers](https://docs.python.org/3/reference/datamodel.html#with-statement-context-managers)
- [PEP 343 — The "with" Statement](https://peps.python.org/pep-0343/)
- [Resource Acquisition Is Initialization](https://en.cppreference.com/w/cpp/language/raii)
