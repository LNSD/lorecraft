---
name: "workspace"
description: "The fixed repository layout lorecraft reads: the root holding docs/__meta__/, corpus directories under docs/, the flat Markdown documents inside them, what is left out without a report, and the one snapshot every command reads. Load when laying out a repository for lorecraft, or asking why a directory or a file is not checked"
type: "meta"
status: "experimental"
components: "module:lorecraft.project.layout,module:lorecraft.project.workspace,module:lorecraft.project.corpus,module:lorecraft.project.aspect"
---

# Workspace Layout

## Summary

lorecraft reads one opinionated layout, and it cannot be configured: documentation lives in `docs/`, its
specifications in `docs/__meta__/`, and each directory beside them is a corpus of flat Markdown documents. A
repository adopts lorecraft by arranging its documentation this way; nothing else registers a corpus or a
document. What lorecraft finds in that layout is the workspace model, which every command reads.

## Table of Contents

1. [Key Concepts](#key-concepts)
2. [Architecture](#architecture)
3. [Limitations](#limitations)
4. [References](#references)

## Key Concepts

- **Root**: The directory that holds `docs/__meta__/`; every path lorecraft prints is relative to it.
- **Corpus**: A directory directly under `docs/` whose documents specifications govern, named by the
  directory.
- **Document**: A Markdown file directly inside a corpus directory.
- **Workspace model**: The corpora, their specifications and their documents, as found in one snapshot.

## Architecture

### The Layout

```text
<root>/
└── docs/
    ├── __meta__/            specifications: <corpus>.md, <corpus>-<namespace>.md, their .json aspects
    ├── feat/                a corpus, governed by docs/__meta__/feat.*
    │   ├── cli.md           a document
    │   └── cli-check.md     a document
    ├── schemas/             no docs/__meta__/schemas.* file, so not a corpus
    └── glossary.md          not inside a corpus, so not a document
```

### Corpora

A directory directly under `docs/` is a corpus when it is a real directory, not a symlink, and at least one
specification file in `docs/__meta__/` sits at its name. A corpus name is lowercase letters, digits and
underscores, starting with a letter or an underscore: `docs/cli_specs/`, never `docs/cli-specs/`, since a
hyphen in a specification's name separates the corpus from a namespace. `docs/__meta__/` is never a corpus.
How the specification files are named and layered is [spec](spec.md)'s subject.

### Documents

A document is a regular Markdown file directly inside a corpus, named in lowercase letters and digits, with
single hyphens or underscores, starting with a letter. The hierarchy between documents is in their names, not
in directories: a corpus is flat.

### Left Out, Not Reported

What the layout does not place is not part of the model, and lorecraft passes over it silently: a directory
under `docs/` that no specification names, a Markdown file at `docs/` itself or in a subdirectory of a corpus,
a symlinked file or corpus directory, and a file whose name does not parse. Only a path named on the command
line is refused with a reason, since it was asked for.

### One Snapshot

A command reads `docs/` and the directories directly in it once, when it starts, and works from that copy,
so it sees one moment of the tree even while files change. A symlink leading outside what the snapshot reads is
recorded, not followed.

## Limitations

- The layout is fixed: `docs/` and `docs/__meta__/` cannot be renamed or moved, and a corpus cannot nest.
- The model covers documentation corpora only; agent skills are not part of it.

## References

- [spec](spec.md) - Related: the specification files in `docs/__meta__/` and how they govern documents
- [cli](cli.md) - Related: the command line that reads the workspace
