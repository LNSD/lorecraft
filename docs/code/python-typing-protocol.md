---
name: "python-typing-protocol"
description: "Choosing between a closed union, a `typing.Protocol` and an ABC by what the checker proves, `collections.abc` types before a custom protocol, no inheriting a protocol's default method, and no `@runtime_checkable`. Load when declaring a `Protocol` or an ABC, choosing between one and a union of records, or annotating a parameter several types satisfy"
type: "core"
scope: "global"
---

# Structural Contracts

**Choose the construct by what the checker must prove about the set of types it admits.** A closed union fixes
the set, so `ty` can prove, at a `match` closed by `assert_never`, that a reader handles each kind. A
`Protocol` leaves the set open, so `ty` proves only that each type has the members. An ABC is open too, but
nominal: only a subclass satisfies it, and `ty` rejects instantiating one that misses an `@abstractmethod`.

How an annotation is spelled, and making an invalid state unrepresentable, are owned by
[python-typing](python-typing.md). This document adds the choice between a closed union, a `Protocol` and an
ABC, and how the shared contract is spelled. When a shared behaviour gets a structural contract at all, and
which members it declares, is owned by [pattern-protocol](pattern-protocol.md).

## 1. A Closed Union When Readers Branch on the Kind, a `Protocol` When They Only Call It

Ask two questions about the set of types. Does a reader need to know which kind it holds, or must the set of
kinds stay fixed? Write a closed union. Does the consumer only call the shared members, and must a new
implementation arrive without editing it? Write a `Protocol`.

| Construct | The set of types | What `ty` proves | Write it when |
|-----------|------------------|------------------|---------------|
| Closed union, `type CheckedFile = CorpusDocument \| SkillFile` | Fixed by the alias | A `match` closed by `assert_never` handles every kind, and a value of an unlisted kind is rejected where the union is expected | Readers branch on the kind |
| `typing.Protocol` | Open: any type with the members | Each value has the members with compatible types; nothing about which type it is | The implementations are independent and the consumer only calls the shared members |
| ABC | Open, but nominal: any subclass | Instantiating a subclass that misses an `@abstractmethod` is rejected; a `match` over the subclasses is not exhaustive | Every implementation is the package's own and must be complete |

Wherever a reader branches on the kind, a closed union is the only choice `ty` checks exhaustively. A kind
added to it is a type error at every `assert_never` until that reader handles it. The goal it serves is owned
by [python-typing](python-typing.md), and the exhaustive `match` by
[python-typing-unreachable](python-typing-unreachable.md).

Nothing can prove that every implementation is handled: `ty` cannot narrow an open set to `Never`, so a
`match` over a protocol-typed value cannot be closed by `assert_never` even when it lists every
implementation. Member access stays type-safe; what is lost is exhaustiveness.

Sharing members is no reason to add a protocol over a union. When every member of a union declares a field,
code reads it straight through the union, with no `match` and no protocol.

An ABC loses exhaustiveness the same way, since any class may subclass it. It fits where the implementations
are the package's own, each must be complete, and no reader branches on which one it holds.

```python
# ❌ Bad — `assert_never` is a type error over a protocol even with every kind listed, so the catch-all written
# instead took `AgentFile`, added later, and every agent file was reported as a skill file
from pathlib import PurePosixPath
from typing import Protocol


class CheckedFile(Protocol):
    """A file the check run reports on."""

    @property
    def path(self) -> PurePosixPath:
        """Where the file is, relative to the workspace root."""


def describe(file: CheckedFile) -> str:
    """Name the file for a finding."""
    match file:
        case CorpusDocument(corpus=corpus):
            return f'{corpus} document {file.path}'
        case SkillFile(skill=skill):
            return f'{skill} skill file {file.path}'
        case _:
            return f'skill file {file.path}'
```

```python
# ✅ Good — the union names every kind, so one added to it is a type error at `assert_never` until `describe`
# handles it; `location` reads the shared `path` through the union without a `match`
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import assert_never


@dataclass(frozen=True, slots=True)
class CorpusDocument:
    """A document of a corpus."""

    path: PurePosixPath
    corpus: str


@dataclass(frozen=True, slots=True)
class SkillFile:
    """A file of an agent skill."""

    path: PurePosixPath
    skill: str


type CheckedFile = CorpusDocument | SkillFile


def describe(file: CheckedFile) -> str:
    """Name the file for a finding."""
    match file:
        case CorpusDocument(corpus=corpus):
            return f'{corpus} document {file.path}'
        case SkillFile(skill=skill):
            return f'{skill} skill file {file.path}'
        case _:
            assert_never(file)


def location(file: CheckedFile) -> str:
    """The file's path, read through the union."""
    return file.path.as_posix()
```

## 2. Spell a Standard Contract With Its `collections.abc` Type

An operation the standard library already names is annotated with its `collections.abc` type, as the table
gives it. Importing them from `collections.abc` is owned by [python-typing](python-typing.md). Preferring an
existing protocol to a custom one is owned by [pattern-protocol](pattern-protocol.md); this section is the
spelling.

| The consumer… | Annotate with |
|---------------|---------------|
| loops over it | `Iterable[T]` |
| also takes its `len` or tests `in` | `Collection[T]` |
| indexes or slices it | `Sequence[T]` |
| looks values up by key | `Mapping[K, V]` |
| calls it | `Callable[[A], R]` |

```python
# ❌ Bad — a protocol restating `Collection`: every reader opened `NameBatch` to learn it was a sized container
from collections.abc import Iterator
from typing import Protocol


class NameBatch(Protocol):
    """Document names that can be counted, tested and listed."""

    def __len__(self) -> int:
        """How many names there are."""

    def __iter__(self) -> Iterator[str]:
        """The names, in order."""

    def __contains__(self, name: object) -> bool:
        """Whether `name` is among the names."""


def summarize(names: NameBatch) -> str:
    """Count and list the names."""
    return f'{len(names)} documents: {", ".join(names)}'
```

```python
# ✅ Good — the standard type states the same contract under a name every reader knows
from collections.abc import Collection


def summarize(names: Collection[str]) -> str:
    """Count and list the names."""
    return f'{len(names)} documents: {", ".join(names)}'
```

## 3. Never Inherit From a Protocol to Share a Default Method

No protocol method carries a body meant to be inherited. Behaviour the implementations share is a module
function that takes the protocol, or, where every implementation is the package's own, an ABC. That an
implementation satisfies a protocol without inheriting from it is owned by
[pattern-protocol](pattern-protocol.md).

A default body reaches only the classes that inherit it. An implementation that satisfies the protocol
structurally does not get it and writes its own, so the shared behaviour forks into copies that drift, and the
protocol no longer says which implementation runs which copy.

```python
# ❌ Bad — `DiskSpecs` inherited the default `first_line`; a cache satisfying the protocol structurally wrote
# its own that skipped blank lines, and the two disagreed on every meta spec opening with one
from pathlib import Path
from typing import Protocol


class SpecSource(Protocol):
    """Where meta specs are read from."""

    def load(self, name: str) -> str:
        """The text of the meta spec `name`."""

    def first_line(self, name: str) -> str:
        """The first line of the meta spec `name`."""
        return self.load(name).splitlines()[0]


class DiskSpecs(SpecSource):
    """Meta specs read from a directory."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def load(self, name: str) -> str:
        """Read the meta spec `name` under the root."""
        return (self.root / name).read_text(encoding='utf-8')
```

```python
# ✅ Good — implementations only satisfy the contract, and every one of them gets the same shared behaviour
from typing import Protocol


class SpecSource(Protocol):
    """Where meta specs are read from."""

    def load(self, name: str) -> str:
        """The text of the meta spec `name`."""


def first_line(source: SpecSource, name: str) -> str:
    """The first line of the meta spec `name`, whichever source holds it."""
    return source.load(name).splitlines()[0]
```

## 4. Do Not Mark a Protocol `@runtime_checkable`

No protocol is decorated `@runtime_checkable`, and no `isinstance` or `issubclass` tests a value against one.
The decorator exists only to make that test possible, and each use of the test has a better home: code that
branches on which kind it holds wants a closed union, and input from outside the process is validated where it
enters. Validating at the edge is owned by [principle-validate-at-edge](principle-validate-at-edge.md), and
why a member-presence check proves so little by [pattern-protocol](pattern-protocol.md).

```python
# ❌ Bad — the test asks only whether a `load` attribute exists, so a configuration naming the `json` module
# passed it, and the first read failed deep in the check run instead of at registration
from typing import Protocol, runtime_checkable


@runtime_checkable
class SpecSource(Protocol):
    """Where meta specs are read from."""

    def load(self, name: str) -> str:
        """The text of the meta spec `name`."""


def register_source(sources: dict[str, SpecSource], name: str, candidate: object) -> None:
    """Register `candidate` under `name` if it is a spec source."""
    if not isinstance(candidate, SpecSource):
        raise TypeError(f'not a spec source: {candidate!r}')
    sources[name] = candidate
```

```python
# ✅ Good — the configuration's source name is parsed into a real source at the edge, where a name like `json`
# is rejected, so registration takes only a `SpecSource` and `ty` checks every call site
from typing import Protocol


class SpecSource(Protocol):
    """Where meta specs are read from."""

    def load(self, name: str) -> str:
        """The text of the meta spec `name`."""


def register_source(sources: dict[str, SpecSource], name: str, source: SpecSource) -> None:
    """Register `source` under `name`."""
    sources[name] = source
```

## Checklist

Before committing code, verify:

- [ ] Every set of kinds a reader branches on is a closed union matched with `assert_never`, never a
      `Protocol`; a `Protocol` appears only where the implementations are independent and consumers only call
      the shared members, and an ABC only where every implementation is the package's own; no protocol is
      added only to read a member every union member already has
- [ ] An operation `collections.abc` names is annotated with that `collections.abc` type
- [ ] No protocol method has a body meant to be inherited; shared behaviour is a function or an ABC
- [ ] No `@runtime_checkable` in the diff, and no `isinstance` or `issubclass` against a protocol

## References

- [python-typing](python-typing.md) - Extends: Owns annotation spelling, making an invalid state
  unrepresentable, the goal a closed union serves, and importing the abstract base classes from
  `collections.abc`
- [pattern-protocol](pattern-protocol.md) - Related: Owns when a shared behaviour gets a structural contract,
  and which members it declares
- [python-typing-unreachable](python-typing-unreachable.md) - Related: Owns the `match` closed by
  `assert_never` that makes a branch over a union exhaustive
- [python-dataclasses](python-dataclasses.md) - Related: Owns the frozen records a closed union's members
  usually are
- [principle-validate-at-edge](principle-validate-at-edge.md) - Foundation: Input from outside the process is
  validated once where it enters

## External References

- [PEP 544 - Protocols: Structural subtyping](https://peps.python.org/pep-0544/)
- [Typing spec - Protocols](https://typing.python.org/en/latest/spec/protocol.html)
- [`collections.abc` - Abstract Base Classes for Containers](https://docs.python.org/3/library/collections.abc.html)
