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
disk, no cache across calls. It knows YAML and, as its target, nothing about what a document, a frontmatter key or a
check is, so the package above it decides what a refused construct means for a document.

## Belongs Here

- Code that scans, parses or refuses YAML text, or builds a value from what a YAML parser reports.
- The subclasses of the YAML library's reader, scanner and parser that make it read the subset Lorecraft accepts.
- The types that name a construct the subset leaves out, and where in the text it is written.
- The tree a YAML text reads into, and the position of each of its nodes, as frozen values of this package's own.
- A fact about YAML's grammar, such as which characters end a line or a token.

## Belongs Elsewhere

| Code that… | Belongs in |
|---|---|
| Reads a file, or any bytes from the disk | `lorecraft.vfs` |
| Names a frontmatter key, a document, a diagnostic code or a line of a document | `lorecraft.project` |
| Words a problem for the people who read a check's report | `lorecraft.project` |
| Is generic over text and knows nothing of YAML, such as where a line ends | `lorecraft.core` |

## Invariants

- The YAML library is imported in this package alone, which a contract in `pyproject.toml` enforces. Two importers
  are named exceptions that the move of event decoding removes: `project.syntax.frontmatter` and
  `project.syntax.syntax_error`, with its unit test. No new importer is added.
- Every other package reads a value, a position or a refusal that this package declares, so an upgrade of the library
  changes this package and no type of it escapes. The target is a position and a problem type of this package's own;
  until the event decoding moves, a refusal still carries the library's `StreamMark`, and the grammar subclasses
  are handed to the decoder.
- It imports no other Lorecraft package than `lorecraft.core`, which the layers contract enforces, so every package
  that reads YAML can import it without a cycle.
- The library's loaders and constructors are never called: no tag resolves and no type is constructed, so the text
  can never build a value beyond what JSON holds.
- It is a pure function of its input. It performs no I/O and holds no state between calls.
- What the subset leaves out is refused as a typed value carrying where it is written, never as a bare library error
  or a bare string.

## Examples

```python
# ❌ Bad — a check imports the library and calls a loader: the library's types and its YAML 1.1 habits now reach
# the checks, and an upgrade edits every place that loads YAML
from ruamel.yaml import YAML


def read_title(block: str) -> str:
    return YAML(typ='safe').load(block)['title']
```

```python
# ✅ Good — the check reads what `lorecraft.yaml` declares, and the library stays behind it
from lorecraft.yaml.basic_yaml import RecordedRefusal


def is_refused(found: object) -> bool:
    return isinstance(found, RecordedRefusal)
```

## Checklist

Before committing code, verify:

- [ ] `ruamel.yaml` is imported only in `lorecraft.yaml` or by the contract's existing named exceptions; no new
      exception is added
- [ ] Nothing in `lorecraft.yaml` reads the disk
- [ ] No library loader or constructor is called, and no new library type becomes part of what the package returns
- [ ] A construct the subset leaves out is a declared refusal that carries its position
- [ ] Nothing added here names a document, a frontmatter key or a diagnostic code

## References

- [adr-001-snapshot-model](../arch/adr-001-snapshot-model.md) - Foundation: The Derivation role
- [adr-017-yaml-parser](../arch/adr-017-yaml-parser.md) - Foundation: The parser is ruamel.yaml's event API
- [principle-single-responsibility](principle-single-responsibility.md) - Foundation: One reason to change
- [principle-information-hiding](principle-information-hiding.md) - Foundation: The library's types stay behind the wrapper
