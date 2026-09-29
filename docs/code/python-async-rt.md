---
name: "python-async-rt"
description: "asyncio as the event loop backend behind the anyio API, the single anyio.run entry point, and where the loop implementation is chosen. Load when starting an event loop, importing asyncio or trio, choosing between asyncio and anyio APIs, or configuring uvloop"
type: "core"
scope: "global"
---

# Async Runtime (`asyncio`)

**`asyncio` is the backend, `anyio` is the API, and one entry point connects them.** Code states what it runs
concurrently in `anyio` terms; which event loop executes it is decided once, where the process starts.

How code behaves inside a task is owned by [python-async](python-async.md). Task lifetime and cancellation are
owned by [python-async-tasks](python-async-tasks.md). This document is
about the runtime.

## 1. Code Speaks `anyio`, and `asyncio` Runs It

Async code is written against `anyio`: task groups, cancel scopes, thread hops, subprocesses, sleeps, and
synchronization primitives all come from it. No module imports `asyncio` or `trio`: the backend is named
once, in the `anyio.run` call of [§2](#2-only-the-entry-point-starts-an-event-loop).

One API throughout keeps one cancellation model throughout. `anyio` cancel scopes are level-triggered: every
`await` inside a cancelled scope raises again. `asyncio` cancellation is edge-triggered, raised once. A helper
written against `asyncio` and called from inside an `anyio` scope follows the wrong model, and the mismatch
shows only during shutdown, which is the path tests exercise least.

```python
# ❌ Bad — an anyio deadline around an asyncio thread hop: the read bypasses the capacity limiter
# the rest of the package is tuned with, and the function answers to two cancellation models
async def read_document(path: Path) -> str:
    with anyio.fail_after(5):
        return await asyncio.to_thread(path.read_text)
```

```python
# ✅ Good — one API, one cancellation model
async def read_document(path: Path) -> str:
    with anyio.fail_after(5):
        return await anyio.to_thread.run_sync(path.read_text)
```

## 2. Only the Entry Point Starts an Event Loop

`anyio.run` is called once per process, in the console script's command handler, and it starts the `asyncio`
backend. Everything below it is an `async def` that its caller awaits. Library code never calls `anyio.run`,
`asyncio.run`, `loop.run_until_complete`, or `asyncio.get_event_loop`. Called from a coroutine that is already
running, as every async test is, starting a loop raises `RuntimeError`, and a library that starts its own
loop cannot be composed into anyone else's.

The loop implementation is chosen at the same place and nowhere else. A faster loop such as `uvloop` is
selected through `backend_options={'use_uvloop': True}` on that one `anyio.run`, never installed globally
through an event loop policy.

```python
# ❌ Bad — the library starts its own loop: an async test calling it raised
# "asyncio.run() cannot be called from a running event loop"
def check_corpus(paths: list[Path]) -> list[Finding]:
    return asyncio.run(check_all(paths))
```

```python
# ✅ Good — the library stays a coroutine, and the command handler owns the one loop
async def check_corpus(paths: list[Path]) -> list[Finding]:
    return await check_all(paths)


def run_check(paths: list[Path]) -> int:
    findings = anyio.run(check_corpus, paths, backend='asyncio')
    return exit_status(findings)
```

## Checklist

Before committing code, verify:

- [ ] No module imports `asyncio` or `trio`; every async API call goes through `anyio`
- [ ] `anyio.run` appears only in a console script's command handler, with `backend='asyncio'`
- [ ] No code calls `asyncio.run`, `run_until_complete`, `get_event_loop`, or `set_event_loop_policy`
- [ ] A loop implementation such as `uvloop` is selected only through `backend_options` on that `anyio.run`

## References

- [python-async](python-async.md) - Extends: Owns the rules for code that runs inside a task
- [python-async-tasks](python-async-tasks.md) - Related: Owns task
  lifetime and the cancel scopes this runtime executes

## External References

- [AnyIO — The basics](https://anyio.readthedocs.io/en/stable/basics.html)
- [Python docs — Runners](https://docs.python.org/3.12/library/asyncio-runner.html)
- [Python docs — Developing with asyncio](https://docs.python.org/3.12/library/asyncio-dev.html)
