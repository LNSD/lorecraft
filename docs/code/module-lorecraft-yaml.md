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
- The tree a YAML text reads into, and the position of each of its nodes, as frozen values of this package's own. A position is one-based, in lines and columns counted in the characters of
  the text, U+FEFF included, and is computed from the index of the library's mark and the text, never from its column.
- A fact about YAML's grammar, such as which characters end a line or a token.
- `reader.read_yaml(text)` and the values it returns, declared in `tree` and `problem`.
- The closed unions that name what a read returns, `YamlProblem`, `RefusedConstruct` and `YamlSyntaxError`, so a caller dispatches over them exhaustively with `match` and `assert_never`, and a `match` over a closed union ends in `assert_never`.

## Belongs Elsewhere

| Code that… | Belongs in |
|---|---|
| Reads a file, or any bytes from the disk | `lorecraft.vfs` |
| Names a frontmatter key, a document, a diagnostic code or a line of a document | `lorecraft.project` |
| Words a problem for the people who read a check's report, such as a refused construct's message and help | `lorecraft.project` |
| Is generic over text and knows nothing of YAML, such as where a line ends | `lorecraft.core` |

## Invariants

- The YAML library is imported in this package alone, which a contract in `pyproject.toml` enforces.
- No function of the package returns, and no value `read_yaml` returns holds, a type of the library, so an upgrade
  changes this package alone. `basic_yaml`, the grammar that holds the library's types, is read inside this package alone, which a
  second contract enforces for every other package, a new one included.
- Every event the library emits is checked once, in `_events`, and read as a frozen value of this package's own, so
  the tree is built from no library event and no loosely typed field. The library's errors and marks are named in
  `basic_yaml`, `_events` and `reader` alone, never in `tree` or `problem`.
- It imports no Lorecraft package other than `lorecraft.core`, which the layers contract enforces, so every package
  that reads YAML can import it without a cycle.
- The library's loaders and constructors are never called: no tag resolves and no type is constructed.
- It is a pure function of its input: no I/O and no state between calls. Its one side effect is debug logging.
- It logs at `debug` only, through `logging.getLogger(__name__)`, with named `extra={'fields': ...}`: sizes, outcomes,
  a construct's type, a position, a syntax error's kind or one of the parser's fixed templates. It never logs the text,
  a scalar, a key or a tag, and sets no handler and no level.
- What the subset leaves out is refused as a typed construct carrying where it is written, never as a bare library
  error or a string. The package names constructs as types and never words them, and nothing in it names frontmatter
  or a diagnostic code.
- A syntax error is returned as a typed kind of this package, never as the parser's message text, which no caller reads.
- A text nested deeper than the interpreter reads is returned as `NestingTooDeepProblem`, which stays positionless.
  `read_yaml` catches the `RecursionError` of its own read, so no exception escapes it; a caller that recurses over the
  tree it returns guards its own recursion.

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

- [ ] No package other than `lorecraft.yaml` imports `lorecraft.yaml.basic_yaml` or `ruamel`, and `just check` runs the contracts that say so
- [ ] Nothing in `lorecraft.yaml` imports a Lorecraft package other than `lorecraft.core`
- [ ] Nothing in `lorecraft.yaml` reads the disk
- [ ] No library loader or constructor is called, and no library type is part of what `read_yaml` returns
- [ ] The tree builder reads the values `_events` declares, never an event of the library, and the library's errors and marks are named in `basic_yaml`, `_events` and `reader` alone
- [ ] A `match` over a closed union ends in `assert_never`, and no dispatch goes through a runtime tuple of classes
- [ ] A construct the subset leaves out is returned as a `RefusedConstructProblem` that carries a `RefusedConstruct` type and its position, never a message
- [ ] A syntax error is returned as a `YamlSyntaxError` kind, never as the parser's problem or context text
- [ ] A position is computed from a mark's index and the text, never read from the mark's column
- [ ] `NestingTooDeepProblem` stays positionless, and no exception escapes `read_yaml`
- [ ] Logging is `debug` only, with named fields and no content of the text, and no handler or level is set
- [ ] Nothing here names a document, a frontmatter key or a diagnostic code, in code, docstrings or tests

## References

- [adr-001-snapshot-model](../arch/adr-001-snapshot-model.md) - Foundation: The Derivation role
- [adr-017-yaml-parser](../arch/adr-017-yaml-parser.md) - Foundation: The parser is ruamel.yaml's event API
- [adr-021-dependency-wrappers](../arch/adr-021-dependency-wrappers.md) - Foundation: Large dependencies stay behind owned wrapper layers
- [principle-single-responsibility](principle-single-responsibility.md) - Foundation: One reason to change
- [principle-information-hiding](principle-information-hiding.md) - Foundation: The library's types stay behind the wrapper
