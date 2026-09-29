---
name: "python-async"
description: "async def only where the body awaits, blocking calls moved off the event loop, and coroutines synchronized with anyio primitives. Load when writing async def or await, calling file, subprocess or sleep APIs from a coroutine, or sharing state between tasks"
type: "core"
scope: "global"
---

# Async Code

**Nothing that runs on the event loop blocks, and a function becomes a coroutine only when it has to.** A
blocking call stalls every task sharing the loop, and a needless `async def` forces every caller to become one
too.

The runtime, and the choice of `anyio` as the API every example here is spelled in, are owned by
[python-async-rt](python-async-rt.md). Task lifetime, cancellation, and deadlines are owned by
[python-async-tasks](python-async-tasks.md). This document is about the code
that runs inside a task.

## 1. A Function Is `async` Only When It Awaits

Declare a function `async def` only when its body awaits something. An `async def` forces every caller to be
async and to await it. A pure function marked async spreads that requirement up the call graph and gains
nothing. Parsing, validation, and formatting stay synchronous, and a coroutine calls them directly.

```python
# ❌ Bad — nothing is awaited, yet every caller of the parser had to become a coroutine
async def parse_frontmatter(text: str) -> dict[str, str]:
    return dict(line.split(': ', 1) for line in text.splitlines())
```

```python
# ✅ Good — the parser stays synchronous, and the coroutine that reads the file calls it
def parse_frontmatter(text: str) -> dict[str, str]:
    return dict(line.split(': ', 1) for line in text.splitlines())


async def load_frontmatter(path: Path) -> dict[str, str]:
    text = await anyio.to_thread.run_sync(path.read_text)
    return parse_frontmatter(text)
```

## 2. Blocking Calls Leave the Loop

A coroutine never makes a blocking call. While it blocks, every other task on the loop waits. File reads and
other blocking library calls go through `anyio.to_thread.run_sync`, a subprocess runs through
`anyio.run_process`, and a pause is `anyio.sleep`, never `time.sleep`. A blocking call is hard to see in
review because nothing marks it: the code reads correctly and simply runs one task at a time.

```python
# ❌ Bad — `subprocess.run` blocks the loop: while git ran, no other document was checked, and
# the concurrency bought nothing
async def document_revision(path: Path) -> str:
    result = subprocess.run(['git', 'log', '-1', '--format=%H', '--', path], capture_output=True)
    return result.stdout.decode()
```

```python
# ✅ Good — the subprocess is awaited, so other documents are checked while git runs
async def document_revision(path: Path) -> str:
    result = await anyio.run_process(['git', 'log', '-1', '--format=%H', '--', path])
    return result.stdout.decode()
```

## 3. Tasks Synchronize With `anyio` Primitives

Tasks share state through `anyio.Lock`, `anyio.Event`, `anyio.Semaphore`, and memory object streams from
`anyio.create_memory_object_stream`, never through the `threading` counterparts. A `threading.Lock` held
across an `await` blocks the whole loop, and the next task that reaches it deadlocks the process. A primitive
belongs to the object or coroutine that uses it, not to the module: module state outlives the event loop, so
every loop the process starts, one per async test, shares the same lock and whatever state a failed run
left in it.

```python
# ❌ Bad — a module-level threading lock held across an await: the second concurrent lookup
# blocked the loop that the first one needed in order to release it
schema_lock = threading.Lock()


async def cached_schema(name: str) -> Schema:
    with schema_lock:
        return await load_schema(name)
```

```python
# ✅ Good — an anyio lock, owned by the cache that uses it; waiting on it yields to other tasks
class SchemaCache:
    def __init__(self) -> None:
        self._lock = anyio.Lock()

    async def get(self, name: str) -> Schema:
        async with self._lock:
            return await load_schema(name)
```

## Checklist

Before committing code, verify:

- [ ] Every `async def` awaits something in its body
- [ ] No coroutine calls `time.sleep`, `subprocess.run`, or a blocking file read outside
      `anyio.to_thread.run_sync`
- [ ] Tasks share state through `anyio` locks, events, semaphores, or memory object streams, never a
      `threading` primitive, and none is created at module level

## References

- [python-async-rt](python-async-rt.md) - Related: Owns the runtime, the entry point, and why the API is
  `anyio`
- [python-async-tasks](python-async-tasks.md) - Related: Owns task
  lifetime, cancellation, and deadlines

## External References

- [AnyIO — Working with threads](https://anyio.readthedocs.io/en/stable/threads.html)
- [AnyIO — Using synchronization primitives](https://anyio.readthedocs.io/en/stable/synchronization.html)
- [AnyIO — Using subprocesses](https://anyio.readthedocs.io/en/stable/subprocesses.html)
