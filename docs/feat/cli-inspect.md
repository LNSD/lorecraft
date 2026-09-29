---
name: "cli-inspect"
description: "lorecraft inspect: printing the workspace model a repository root declares, its corpora, their specification stems and files, and the stems governing each document, as a tree or as JSON. Load when asking which specifications govern a document, why a document is not checked, or scripting against the workspace model"
type: "feature"
status: "experimental"
components: "module:lorecraft.cli.commands.inspect,module:lorecraft.cli.workspace_tree,module:lorecraft_project.workspace"
---

# `lorecraft inspect`

## Summary

`lorecraft inspect` shows what a repository declares under `docs/`, as the checks see it: each corpus, the
specification stems in `docs/__meta__/` that belong to it with their files, and every document with the stems
that govern it. It answers why a document is or is not checked, without running a check.

## Table of Contents

1. [Key Concepts](#key-concepts)
2. [Configuration](#configuration)
3. [Usage](#usage)
4. [Limitations](#limitations)
5. [References](#references)
6. [Code References](#code-references)

## Key Concepts

- **Workspace model**: The corpora a root declares and their documents, loaded from one snapshot, as
  [workspace](workspace.md) lays out.
- **Specification stem**: A filename in `docs/__meta__/` without its extensions, such as `feat-cli`, with the
  files that share it.
- **Governed by**: The stems whose rules apply to a document, broad to narrow.

## Configuration

| Argument or option | Default | Description |
|--------------------|---------|-------------|
| `ROOT`             | `.`     | The workspace root to inspect; it must be an existing directory |
| `--json`           | off     | Print the model as JSON instead of drawing it |

`ROOT` is taken as given: unlike `lorecraft check`, `inspect` does not search the parents for `docs/__meta__/`.

## Usage

```bash
# Draw the model of the current directory
lorecraft inspect

# The model of another root, as JSON
lorecraft inspect ../other-repo --json
```

### Output

The text form is a tree on stdout, rooted at the absolute root path. A document's stems follow it in
brackets. An excerpt, from this repository:

```text
└── feat (docs/feat)
    ├── specs (2)
    │   ├── feat: feat.header.json, feat.md, feat.structure.json
    │   └── feat-cli: feat-cli.header.json, feat-cli.md, feat-cli.structure.json
    └── documents (5)
        ├── cli.md [feat, feat-cli]
        ├── cli-check.md [feat, feat-cli]
```

With `--json`, stdout is one object: `root`, and `corpora`, each with `name`, `directory`, `specs` as `stem`
and `files`, and `documents` as `path` and `governed_by`. Paths are root-relative.

```json
{"path": "docs/feat/cli-check.md", "governed_by": ["feat", "feat-cli"]}
```

A root with no `docs/__meta__/` prints a model with no corpora, and exits `0`.

### Exit Status

| Code | Meaning |
|------|---------|
| `0`  | The model was printed |
| `1`  | The model could not be loaded: an entry that cannot be read, or a specification file that cannot be decoded or states no usable rules. The error goes to stderr, prefixed `error:` |
| `2`  | A usage error, including a `ROOT` that is not an existing directory |

```text
error: invalid JSON in schema docs/__meta__/feat.header.json: Expecting property name enclosed in double quotes
```

## Limitations

- The model covers the documentation corpora only; skills under `.agents/skills/` are not part of it.
- A file the model [leaves out](workspace.md#left-out-not-reported), such as a Markdown file in a
  subdirectory of a corpus, is not shown at all.

## References

- [cli](cli.md) - Base: the command line and the options every command shares
- [workspace](workspace.md) - Dependency: the layout the model is read from
- [spec](spec.md) - Related: how a stem selects the corpus and the documents it governs
- [cli-check](cli-check.md) - Related: the checks that read the same model

## Code References

- `packages/lorecraft/src/lorecraft/cli/commands/inspect.py` - Declares the command, loads the model
- `packages/lorecraft/src/lorecraft/cli/workspace_tree.py` - Draws the tree and renders the JSON
- `packages/lorecraft-project/src/lorecraft_project/workspace/` - The workspace model and its loader
