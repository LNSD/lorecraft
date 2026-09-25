---
name: "pattern-protocol"
description: "Describe a small shared behavior through structural typing without requiring inheritance. Load when two independent implementations serve one consumer, a concrete annotation excludes a valid implementation, or a custom interface is being proposed"
type: "core"
scope: "global"
---

# Protocol (Structural Contract)

## Rule

Annotate a consumer with the smallest behavior it needs. Prefer an existing protocol from
`collections.abc`, such as `Iterable`, `Mapping`, or `Callable`, when it states that behavior.
Define a custom `typing.Protocol` only when multiple real implementations need the same
contract and no existing protocol expresses it. Declare only the members the consumer uses;
implementations satisfy the contract through their members without inheriting from it.

Keep runtime validation separate from static typing. A protocol annotation does not check
values at runtime. Even `@runtime_checkable` checks member presence, not signatures or return
types, so validate untrusted input at its boundary instead of treating `isinstance(value,
SomeProtocol)` as proof of a full contract.

## Examples

1. **Use an existing protocol for an ordinary operation.** A report needs to traverse names,
   regardless of which collection supplies them.

```python
# ❌ Bad — the concrete list annotation excludes other collections the loop can use.
def render_names(names: list[str]) -> str:
    return ', '.join(names)
```

```python
# ✅ Good — Iterable states the only behavior the consumer requires.
from collections.abc import Iterable


def render_names(names: Iterable[str]) -> str:
    return ', '.join(names)
```

2. **Define a custom contract for independent implementations.** Two sources provide text
   to the same reader, but neither needs to inherit from a shared base class.

```python
# ❌ Bad — the reader rejects another source with the same load operation.
def read_title(source: DirectorySource, name: str) -> str:
    return source.load(name).splitlines()[0]
```

```python
# ✅ Good — independent sources satisfy the reader's narrow contract structurally.
from pathlib import Path
from typing import Protocol


class TextSource(Protocol):
    def load(self, name: str) -> str: ...


class DirectorySource:
    def __init__(self, root: Path) -> None:
        self.root = root

    def load(self, name: str) -> str:
        return (self.root / name).read_text(encoding='utf-8')


class MemorySource:
    def __init__(self, texts: dict[str, str]) -> None:
        self.texts = texts

    def load(self, name: str) -> str:
        return self.texts[name]


def read_title(source: TextSource, name: str) -> str:
    return source.load(name).splitlines()[0]
```

## Why It Matters

A concrete annotation can reject a valid collaborator even when the consumer uses only a
shared operation. A narrow protocol makes that operation visible to readers and type
checkers without coupling independent implementations through inheritance. Existing
collection protocols avoid a project-specific interface for behavior Python already names.

## Pragmatism Caveat

Use the concrete type while there is one implementation. Do not create a protocol solely to
inject a dependency or replace a simple function. If implementations need shared behavior or
state, an ordinary base class may fit better. A structural contract does not promise semantic
equivalence: tests still need to check that implementations behave as the consumer expects.

## Checklist

- [ ] An existing `collections.abc` protocol is used when it expresses the required behavior
- [ ] A custom protocol has multiple real implementations and declares only consumed members
- [ ] Implementations are not forced to inherit from the protocol
- [ ] Runtime input validation does not rely on a protocol annotation or member-presence check
- [ ] Tests cover the behavior each implementation promises to the consumer

## References

- [pattern-dependency-injection](pattern-dependency-injection.md) - Related: Supply collaborators explicitly without inventing an interface for one implementation
- [pattern-composite](pattern-composite.md) - Related: Give leaves and groups a shared operation when processing a tree

## External References

- [Python docs — Protocols and structural subtyping](https://docs.python.org/3.12/library/typing.html#nominal-vs-structural-subtyping)
- [Python docs — Runtime-checkable protocols](https://docs.python.org/3.12/library/typing.html#typing.runtime_checkable)
