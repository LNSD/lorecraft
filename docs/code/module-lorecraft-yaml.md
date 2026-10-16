---
name: "module-lorecraft-yaml"
description: "The lorecraft.yaml package's responsibility, role, boundary and invariants: the one wrapper around YAML syntax and parsing, which owns every YAML operation and keeps the YAML library's types from reaching any other package. Load when adding or moving code in lorecraft.yaml, reading or changing how YAML text is scanned, parsed or refused, or importing ruamel.yaml anywhere"
type: "pkg"
scope: "pkg:lorecraft.yaml"
---

# The `lorecraft.yaml` Package

## Responsibility

Wrap YAML syntax and parsing, so that every YAML operation Lorecraft performs goes through it. It changes when the
YAML subset Lorecraft reads changes, or when the YAML library behind it does.

## Role

**Derivation.** It turns the text of a YAML block into what that text says, a pure function of the text: no
disk, no cache across calls. It knows YAML and nothing about what a document, a frontmatter key or a
check is, so the package above it decides what a refused construct means for a document.

## Belongs Here

- Code that scans, parses or refuses YAML text, or builds a value from what a YAML parser reports.
- The subclasses of the YAML library's reader, scanner and parser that make it read the subset Lorecraft accepts.
- The types that name a construct the subset leaves out, as the facts a caller words it from, and where in the text it is written.
- The tree a YAML text reads into, and the position of each of its nodes, as frozen values of this package's own.
- A fact about YAML's grammar, such as which characters end a line or a token.
- `reader.read_yaml(text)` and the values it returns, declared in `tree` and `problem`.
- Dispatch over problems exhaustively with `match` and `assert_never`, never through runtime tuples of problem classes.

## Belongs Elsewhere

| Code that… | Belongs in |
|---|---|
| Reads a file, or any bytes from the disk | `lorecraft.vfs` |
| Names a frontmatter key, a document, a diagnostic code or a line of a document | `lorecraft.project` |
| Words a problem for the people who read a check's report, such as a refused construct's message and help | `lorecraft.project` |
| Is generic over text and knows nothing of YAML, such as where a line ends | `lorecraft.core` |

## Invariants

- The YAML library is imported in this package alone, which a contract in `pyproject.toml` enforces.
- Every other package reads a value, a position or a problem that this package declares, so an upgrade of the library
  changes this package and no type of it escapes. The grammar module that holds the library's types is read inside
  this package alone, which a second contract enforces.
- Every value the library hands over, an event's fields and an error's texts, is checked once, in `_events`, and read
  as a frozen value of this package's own, so nothing past that seam reads an `Any`.
- It imports no other Lorecraft package than `lorecraft.core`, which the layers contract enforces, so every package
  that reads YAML can import it without a cycle.
- The library's loaders and constructors are never called: no tag resolves and no type is constructed, so the text
  can never build a value beyond what JSON holds.
- It is a pure function of its input. It performs no I/O and holds no state between calls.
- What the subset leaves out is refused as a typed construct carrying where it is written, never as a bare library error
  or a string. The package names constructs as types and never words them, and no docstring or code names frontmatter or a
  diagnostic code.

## Examples

```python
# ❌ Bad — a check imports the library and calls a loader: the library's types and its YAML 1.1 habits now reach
# the checks, and an upgrade edits every place that loads YAML
from ruamel.yaml import YAML


def read_title(block: str) -> str:
    return YAML(typ='safe').load(block)['title']
```

```python
# ✅ Good — the check reads what `lorecraft.yaml` returns, and the library and its grammar stay behind it
from lorecraft.yaml.problem import RefusedConstructProblem
from lorecraft.yaml.reader import read_yaml


def is_refused(block: str) -> bool:
    return isinstance(read_yaml(block), RefusedConstructProblem)
```

## Checklist

Before committing code, verify:

- [ ] No package other than `lorecraft.yaml` imports `lorecraft.yaml.basic_yaml` or `ruamel`
- [ ] Nothing in `lorecraft.yaml` reads the disk
- [ ] No library loader or constructor is called, and no library type is part of what the package returns
- [ ] The tree builder reads the values `_events` declares, never an event or an error of the library
- [ ] Problems are dispatched exhaustively with `match` and `assert_never`, never through runtime tuples
- [ ] A construct the subset leaves out is returned as a `RefusedConstructProblem` that carries a `RefusedConstruct` type and its position, never a message
- [ ] Nothing here names a document, a frontmatter key or a diagnostic code, in code, docstrings or tests

## References

- [adr-001-snapshot-model](../arch/adr-001-snapshot-model.md) - Foundation: The Derivation role
- [adr-017-yaml-parser](../arch/adr-017-yaml-parser.md) - Foundation: The parser is ruamel.yaml's event API
- [adr-021-dependency-wrappers](../arch/adr-021-dependency-wrappers.md) - Foundation: Large dependencies stay behind owned wrapper layers
- [principle-single-responsibility](principle-single-responsibility.md) - Foundation: One reason to change
- [principle-information-hiding](principle-information-hiding.md) - Foundation: The library's types stay behind the wrapper
