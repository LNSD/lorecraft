---
name: "pattern-command"
description: "An operation carries the inputs needed for later execution as a named value. Load when work must be queued, retried, audited, or undone after the caller that requested it has returned"
type: "core"
scope: "global"
---

# Command (Deferred Operation)

## Rule

Represent an operation as a command when it must outlive the call that requested it. Give the command a
name, the inputs needed to run, and one execution method. Capture those inputs when the command is created
so later execution does not depend on a caller's changing local variables. Keep the executor responsible
for when and how commands run; the command owns what one operation does.

For an in-process queue, a frozen dataclass can make the pending operation inspectable. If a queue must
survive a process restart, store serializable command data and resolve the executable collaborator at run
time. Include a stable operation identifier when retries could repeat an external side effect. A normal CLI
handler is not automatically this pattern: it becomes a command object only when it needs a separate life
after invocation.

## Examples

A batch schedules document reads for later execution:

```python
# ❌ Bad — every closure reads the final value of path when the batch runs.
from collections.abc import Callable
from pathlib import Path


def schedule(paths: list[Path]) -> list[Callable[[], str]]:
    jobs: list[Callable[[], str]] = []
    for path in paths:
        jobs.append(lambda: path.read_text(encoding='utf-8'))
    return jobs
```

```python
# ✅ Good — each command captures one path and exposes the pending operation.
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ReadDocument:
    path: Path

    def execute(self) -> str:
        return self.path.read_text(encoding='utf-8')


def schedule(paths: list[Path]) -> list[ReadDocument]:
    return [ReadDocument(path) for path in paths]
```

## Why It Matters

Separating request time from execution time lets a queue control order, retries, and reporting. A named
command carries its inputs visibly, so a reviewer can see what will happen later. Capturing values at
creation prevents a deferred operation from acting on a variable that has since changed.

## Pragmatism Caveat

For immediate work, call the function directly. A simple `functools.partial` or a closure with captured
values can serve a small in-process queue when commands need no inspection, persistence, or operation-specific
behavior. Do not add command classes solely because a CLI has subcommands. Retries of side effects require
an explicit idempotency policy; a command object alone does not make them safe.

## Checklist

- [ ] Execution genuinely occurs after or apart from the request that created it
- [ ] The command captures all required input values at creation
- [ ] The execution method performs one named operation and leaves scheduling to the executor
- [ ] Persistent queues store serializable data rather than a callable or live resource
- [ ] Retried external side effects have a stated idempotency policy

## References

- [principle-least-surprise](principle-least-surprise.md) - Foundation: The command name and inputs predict its effect
- [pattern-dependency-injection](pattern-dependency-injection.md) - Related: Supply an executor or receiver explicitly when execution needs one
- [pattern-registry](pattern-registry.md) - Related: A CLI registry routes immediate handlers; a command represents deferred work

## External References

- [Refactoring.Guru — Command](https://refactoring.guru/design-patterns/command)
- [Python docs — `functools.partial`](https://docs.python.org/3.12/library/functools.html#functools.partial)
