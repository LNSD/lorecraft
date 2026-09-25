---
name: "pattern-structured-concurrency"
description: "Concurrent child work is owned by a scope that waits for it, propagates its failure, and cancels it. Load when starting tasks or threads, when using asyncio.create_task, gather, TaskGroup or an executor, or when catching CancelledError"
type: "core"
scope: "global"
---

# Structured Concurrency (Scoped Child Work)

## Rule

Every concurrent unit of work has a visible owner, and the owner's scope does not end until the work has
finished. When the scope exits, each child has completed, failed with its failure propagated, or been
cancelled. No task or thread outlives the block that started it unless it is handed to a longer-lived owner
that makes the same guarantee.

In `asyncio`, start related tasks inside `async with asyncio.TaskGroup() as group`. The group awaits every task
at block exit; when one fails, it cancels the others, waits for them, and raises an `ExceptionGroup`, handled
with `except*`. Do not call `asyncio.create_task` and drop the result: the event loop holds tasks by weak
reference, so an unreferenced task can disappear mid-run, and its exception is never seen.

With threads, submit work inside `with ThreadPoolExecutor(...) as pool` and call `.result()` on every future,
so a worker's exception reaches the caller rather than staying inside an unread future.

Cancellation is how the scope stops its children. Never swallow `asyncio.CancelledError`: catch it only to
clean up, then re-raise. Put cleanup in `try`/`finally`, which runs on cancellation as on any other exit.

`asyncio.gather` is acceptable when independent jobs should keep running after one fails, with
`return_exceptions=True` so every outcome is collected and inspected. It does not cancel siblings.

## Examples

1. **Fire-and-forget tasks**
   Documents are checked concurrently.

```python
# ❌ Bad — the tasks are not awaited: the function returns before they finish, a failure is
# logged as "Task exception was never retrieved" at shutdown, and the findings are lost.
async def check_corpus(paths: list[Path]) -> None:
    for path in paths:
        asyncio.create_task(check_document(path))
```

```python
# ✅ Good — the group owns every task; the function returns only when all are done, and a
# failure cancels the rest and propagates.
async def check_corpus(paths: list[Path]) -> list[Finding]:
    async with asyncio.TaskGroup() as group:
        tasks = [group.create_task(check_document(path)) for path in paths]
    return [finding for task in tasks for finding in task.result()]
```

2. **Swallowed cancellation**

```python
# ❌ Bad — the watcher ignores cancellation, so the enclosing TaskGroup waits forever on shutdown.
async def watch(queue: asyncio.Queue[Path]) -> None:
    while True:
        try:
            await recheck(await queue.get())
        except asyncio.CancelledError:
            continue
```

```python
# ✅ Good — cleanup runs in `finally`; the cancellation propagates to the owner.
async def watch(queue: asyncio.Queue[Path]) -> None:
    try:
        while True:
            await recheck(await queue.get())
    finally:
        await flush_report()
```

## Why It Matters

Unowned work fails invisibly, finishes after the result was reported, or keeps the process alive after it
should exit. A scope that owns its children makes the lifetime readable from the code's indentation, delivers
every failure to a caller, and gives shutdown one mechanism that reaches everything.

## Pragmatism Caveat

Sequential code needs none of this; do not add concurrency to a loop that is fast enough. A single awaited
call is already structured. A deliberately long-lived background task still needs an owner, such as a group
spanning the application's run.

## Checklist

- [ ] Every task is created in a `TaskGroup` or held and awaited by an owner
- [ ] Every thread-pool future's `.result()` is read inside the executor's `with` block
- [ ] Failures from a task group are handled with `except*`
- [ ] `CancelledError` is never swallowed; cleanup lives in `finally`
- [ ] `gather` is used only for independent jobs, with every outcome inspected

## References

- [pattern-resource-lifecycle](pattern-resource-lifecycle.md) - Related: A task scope is released on every exit path, like any resource
- [pattern-bounded-work-queue](pattern-bounded-work-queue.md) - Related: Workers draining a queue run inside such a scope
- [python-errors-handling](python-errors-handling.md) - Related: Owns how caught exceptions are handled

## External References

- [Python docs — Task Groups](https://docs.python.org/3.12/library/asyncio-task.html#task-groups)
- [Python docs — Creating Tasks](https://docs.python.org/3.12/library/asyncio-task.html#creating-tasks)
- [Python docs — Task Cancellation](https://docs.python.org/3.12/library/asyncio-task.html#task-cancellation)
- [Nathaniel J. Smith — Notes on structured concurrency](https://vorpus.org/blog/notes-on-structured-concurrency-or-go-statement-considered-harmful/)
