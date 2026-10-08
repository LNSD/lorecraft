---
name: "module-lorecraft-core"
description: "The lorecraft.core package's responsibility, role, boundary and invariants: the project's standard library, generic infrastructure every other package builds on, with no knowledge of Lorecraft's domain. Load when adding or moving code in lorecraft.core, or deciding whether a generic helper, value type or error base belongs there"
type: "pkg"
scope: "pkg:lorecraft.core"
---

# The `lorecraft.core` Package

## Responsibility

Provide the generic infrastructure the other packages are built on: the project's standard library. It changes
when a generic building block is added or changes shape, never because something about documents, skills,
agents or checks changed.

## Role

**Base.** Every package imports `lorecraft.core`, the way every module imports the standard library. So what it
holds is generic: it would read the same in any tool of this kind, and it knows nothing of what Lorecraft is
for. The rest of the project specializes it. It never specializes the rest of the project.

## Belongs Here

- Generic code that you can describe without naming a document, a meta spec, a skill, an agent, a check or
  the disk.
- A value type the other packages spell their arguments and answers in, together with the rule that proves it
  valid when it is constructed.
- A generic immutable collection a value type can hold, such as a mapping that compares and hashes by its items.
- The error base that every failure family derives from, and the errors raised by this package's own code.
- A small generic helper that more than one package would otherwise write again.

## Belongs Elsewhere

A standard library is specialized by the code that uses it, never the other way round. Code that specializes a
generic building block for one domain belongs in the package that owns that domain:

| Code that… | Belongs in |
|---|---|
| Specializes it for a fixed directory or suffix of the layout | `lorecraft.layout` |
| Specializes it for documents, corpora, meta specs or skills | `lorecraft.project` |
| Specializes it for an agent or a directory an agent reads | `lorecraft.agents` |
| Specializes it for the disk, even only to check that a path exists | `lorecraft.vfs` |
| Specializes it for the command line, its output or its exit codes | `lorecraft.cli` |
| Specializes the error base for another package's operation | Beside the code that raises it |

## Invariants

- Like a standard library, it depends on nothing that builds on it: `lorecraft.core` imports no other Lorecraft
  package, which the layers contract enforces, so every package can import it without a cycle.
- Importing it is free and calling it has no effect beyond its result: it performs no I/O and holds no mutable
  module state.
- Every value type is immutable and proves its invariant when it is constructed, so code holding one never
  checks it again, whichever package it travels through.
- A generic value stays generic. The path value holds no `Path` and never resolves a symlink: following a symlink is
  the filesystem's specialization, owned by `lorecraft.vfs`.
- Each submodule is its own entry point, imported by its full name, such as `lorecraft.core.path`. The package's
  `__init__.py` re-exports nothing, an exception to [python-modules](python-modules.md) §6, so a building block
  added to one submodule never grows a surface every package shares.

## Examples

```python
# ❌ Bad — the generic path value learns what a document is: every package now inherits the document suffix,
# and changing the suffix edits the standard library the whole project builds on
@dataclass(frozen=True, slots=True, order=True)
class WorkspacePath:
    parts: tuple[str, ...]

    def is_document(self) -> bool:
        return self.parts[-1].endswith('.md')
```

```python
# ✅ Good — the path stays generic; the layout that fixes the document suffix specializes it
MARKDOWN_SUFFIX: Final[str] = '.md'


def is_document_path(path: WorkspacePath) -> bool:
    return path.parts[-1].endswith(MARKDOWN_SUFFIX)
```

## Checklist

Before committing code, verify:

- [ ] Everything added to `lorecraft.core` is generic: you can describe it without naming a document, a
      meta spec, a skill, an agent, a check or the disk
- [ ] Nothing added imports a package that builds on `lorecraft.core`, performs I/O, or keeps state between calls
- [ ] A new value type is immutable and validates when it is constructed
- [ ] Nothing added specializes a building block for one domain; that specialization lives in the domain's package
- [ ] An error declared here is the base, or is raised by `lorecraft.core`'s own code
- [ ] Nothing is re-exported from `lorecraft.core`'s `__init__.py`; callers import the submodule that declares it

## References

- [adr-001-snapshot-model](../arch/adr-001-snapshot-model.md) - Foundation: The Base role
- [principle-single-responsibility](principle-single-responsibility.md) - Foundation: One reason to change
- [pattern-value-object](pattern-value-object.md) - Foundation: A value that proves itself at construction
