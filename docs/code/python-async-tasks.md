---
name: "python-async-tasks"
description: "anyio task groups own their child tasks, collect their results, and propagate their failures; cancel scopes set deadlines; cancellation is re-raised and cleanup is shielded. Load when starting tasks, using create_task_group, start_soon, fail_after, move_on_after or CancelScope, or catching a cancellation exception"
type: "core"
scope: "pkg:pypi/anyio"
---

# Structured Concurrency (`anyio`)

**Every task has a visible owner, and the owner's block does not end until the task has.** When an
`async with anyio.create_task_group()` block exits, each child has completed, failed with its failure
propagated, or been cancelled. No task outlives the block that started it unless it is handed to a
longer-lived group that makes the same guarantee.

The runtime and the choice of `anyio` are owned by [python-async-rt](python-async-rt.md). What code may do
inside a task is owned by [python-async](python-async.md). This document is about task lifetime.

## 1. Start Tasks Only in a Task Group

Start concurrent work with `group.start_soon` inside `async with anyio.create_task_group() as group`. The
group waits for every child at block exit. When one fails, it cancels the others, waits for them, and raises
an `ExceptionGroup`, handled with `except*`. Never call `asyncio.create_task` or `asyncio.ensure_future`: the
task has no owner, its failure is reported only at shutdown, if at all, and the function returns before it
finishes.

`start_soon` returns nothing. A child delivers its result by writing into a collection the caller owns, which
the caller reads once the block has exited.

```python
# ❌ Bad — the tasks are not awaited: the function returns before they finish, a failure is
# logged as "Task exception was never retrieved" at shutdown, and the findings are lost
async def check_corpus(paths: list[Path]) -> None:
    for path in paths:
        asyncio.create_task(check_document(path))
```

```python
# ✅ Good — the group owns every task; the function returns only when all are done, and a
# failure cancels the rest and propagates
async def check_into(path: Path, findings: list[Finding]) -> None:
    findings.extend(await check_document(path))


async def check_corpus(paths: list[Path]) -> list[Finding]:
    findings: list[Finding] = []
    async with anyio.create_task_group() as group:
        for path in paths:
            group.start_soon(check_into, path, findings)
    return findings
```

## 2. A Task the Caller Depends On Is Started With `group.start`

When the caller needs a child to be ready before it continues, such as a server that must be listening, use
`await group.start(fn)`. The child takes a `task_status: anyio.abc.TaskStatus[T] = anyio.TASK_STATUS_IGNORED`
parameter and calls `task_status.started(value)` when it is ready. `start` returns that value and leaves the
child running in the group. A sleep before the next step guesses at readiness, and it guesses wrong on a slow
CI runner.

```python
# ✅ Good — the caller continues only once the watcher is subscribed, and the group still owns it
async def watch_corpus(
    root: Path,
    *,
    task_status: anyio.abc.TaskStatus[None] = anyio.TASK_STATUS_IGNORED,
) -> None:
    async with subscribe(root) as changes:
        task_status.started()
        async for path in changes:
            await recheck(path)


async def serve(root: Path) -> None:
    async with anyio.create_task_group() as group:
        await group.start(watch_corpus, root)
        await announce_ready()
```

## 3. Every Wait on the Outside World Has a Deadline

An `await` on a network peer, a subprocess, or another process's output sits inside
`with anyio.fail_after(s)`, which raises `TimeoutError`, or `with anyio.move_on_after(s)` when running out of
time is an expected outcome the caller checks through the scope's `cancelled_caught`. Without a deadline, a
peer that never answers stalls the task and every owner above it. Set the deadline at the call site that
knows the budget, not inside a helper that cannot.

```python
# ❌ Bad — a schema server that accepted the connection and never replied kept the check running
# until CI killed the job
async def fetch_schema(stream: anyio.abc.ByteReceiveStream) -> bytes:
    return await stream.receive()
```

```python
# ✅ Good — the wait is bounded, and the caller sees a TimeoutError it can report
async def fetch_schema(stream: anyio.abc.ByteReceiveStream) -> bytes:
    with anyio.fail_after(10):
        return await stream.receive()
```

## 4. Cancellation Is Re-raised, and Cleanup That Awaits Is Shielded

Cancellation is how a group stops its children, so it always reaches the group. Catch
`anyio.get_cancelled_exc_class()` only to clean up, then re-raise it; never write
`except asyncio.CancelledError`. Cleanup goes in `finally`. Because cancellation is level-triggered, an
`await` in a `finally` block of a cancelled task is itself cancelled at once, so cleanup that awaits runs
inside `with anyio.CancelScope(shield=True)`. Bound shielded cleanup with `anyio.move_on_after`, since a
shield also blocks the cancellation that would end a hung cleanup.

```python
# ❌ Bad — the watcher swallows cancellation, so the enclosing group waits forever on shutdown
async def watch(changes: MemoryObjectReceiveStream[Path]) -> None:
    while True:
        try:
            await recheck(await changes.receive())
        except anyio.get_cancelled_exc_class():
            continue
```

```python
# ✅ Good — cancellation propagates to the group, and the report is flushed under a bounded shield
async def watch(changes: MemoryObjectReceiveStream[Path]) -> None:
    try:
        async for path in changes:
            await recheck(path)
    finally:
        with anyio.move_on_after(5, shield=True):
            await flush_report()
```

## 5. Independent Jobs Record Their Own Failures

When every job must run even if another fails, each child catches its own expected failure and records it,
inside the same group. Letting the failure escape cancels the siblings, and `anyio` has no counterpart to
`gather(return_exceptions=True)` to fall back on. Catch the specific exception the job can raise, not
`Exception`, so a defect still stops the group.

```python
# ✅ Good — one unreadable document is reported, and the rest are still checked
async def check_each(path: Path, results: dict[Path, list[Finding] | OSError]) -> None:
    try:
        results[path] = await check_document(path)
    except OSError as exc:
        results[path] = exc
```

## Checklist

Before committing code, verify:

- [ ] Every task is started with `start_soon` or `start` inside `anyio.create_task_group`, and no code calls
      `asyncio.create_task` or `ensure_future`
- [ ] Results from `start_soon` children land in a collection the caller reads after the block exits
- [ ] A child the caller waits on is started with `group.start` and calls `task_status.started`
- [ ] Failures from a task group are handled with `except*`
- [ ] Every `await` on a network peer or subprocess is inside `fail_after` or `move_on_after`
- [ ] The cancellation exception is caught only as `anyio.get_cancelled_exc_class()` and always re-raised
- [ ] Cleanup that awaits sits in `finally` under a bounded `move_on_after(..., shield=True)`
- [ ] Jobs that must all run catch and record their own specific exceptions inside the group

## References

- [python-async](python-async.md) - Extends: Owns the rules for code that runs inside a task
- [python-async-rt](python-async-rt.md) - Related: Owns the runtime that executes these cancel scopes
- [pattern-resource-lifecycle](pattern-resource-lifecycle.md) - Related: A task group is released on every
  exit path, like any resource
- [error-handling](error-handling.md) - Related: Owns how caught exceptions are handled

## External References

- [AnyIO — Creating and managing tasks](https://anyio.readthedocs.io/en/stable/tasks.html)
- [AnyIO — Cancellation and timeouts](https://anyio.readthedocs.io/en/stable/cancellation.html)
- [Nathaniel J. Smith — Notes on structured concurrency](https://vorpus.org/blog/notes-on-structured-concurrency-or-go-statement-considered-harmful/)
