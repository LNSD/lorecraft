---
name: "cli-inspect"
description: "lorecraft inspect: printing the workspace model a repository root declares, its corpora, their specification stems and files, the stems governing each document, and the agent skills with the agents that read them, as a tree or as JSON. Load when asking which specifications govern a document, why a document is not checked, which agents read a skill, or scripting against the workspace model"
type: "feature"
status: "experimental"
components: "module:lorecraft.cli.commands.inspect,module:lorecraft.cli.workspace_tree,module:lorecraft.project.workspace"
---

# `lorecraft inspect`

## Summary

`lorecraft inspect` shows what a repository declares, as the checks see it: each corpus under `docs/`, the
specification stems in `docs/__meta__/` that belong to it with their files, and every document with the stems
that govern it; then each agent's skills directory and every skill with the agents that read it. It answers
why a document is or is not checked, and which agents see a skill, without running a check.

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
- **Governed by**: The specifications whose rules apply to a document, broad to narrow: their stems in the
  tree, and every file at those stems in the JSON.
- **Agent skills directory**: A directory an agent reads skills from, such as `.claude/skills`, shown only when
  the root has it, with the real directory it leads to when it is a symlink.
- **Skill**: A directory directly inside an agent skills directory that holds a `SKILL.md`.

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
    │   ├── feat: feat.md, feat.structure.json
    │   └── feat-cli: feat-cli.md, feat-cli.structure.json
    └── documents (5)
        ├── cli.md [feat, feat-cli]
        ├── cli-check.md [feat, feat-cli]
```

With `--json`, stdout is one object. It holds `root`, and `corpora`, each with `name`, `directory`, `specs` as
`stem` and `files`, and `documents` as `path` and `governed_by`. `governed_by` lists the files of each governing
stem, broad to narrow, so a reader opens a document's specifications without mapping a stem to its files. Paths
are root-relative.

```json
{
  "path": "docs/feat/cli-check.md",
  "governed_by": [
    "docs/__meta__/feat.md",
    "docs/__meta__/feat.structure.json",
    "docs/__meta__/feat-cli.md",
    "docs/__meta__/feat-cli.structure.json"
  ]
}
```

The skills follow the corpora. An agent skills directory that is a symlink names where it leads, and a
skill is followed by the agents that read it in brackets. A skill that is itself a symlink, to another skill
or to a directory elsewhere in the repository, is listed where the agent finds it:

```text
├── agent skills directories (2)
│   ├── claude-code: .claude/skills -> .agents/skills
│   └── codex: .agents/skills
└── skills (2)
    ├── .agents/skills/commit [claude-code, codex]
    └── .agents/skills/docs-rules [claude-code, codex]
```

In the JSON these are `agent_skills_dirs`, each with `agent`, `path` and `resolves_to`, and `skills`, each with
the `path` of its `SKILL.md` and its `agents`.

A root with no `docs/__meta__/` prints a model with no corpora, a root with no skills directory one with no
skills, and both exit `0`.

### Exit Status

| Code | Meaning |
|------|---------|
| `0`  | The model was printed |
| `1`  | The model could not be loaded: an entry that cannot be read, under `docs/` or a skills directory, a `docs/` or `docs/__meta__/` that is a [symlink](workspace.md#one-snapshot), or a specification file that cannot be decoded or states no usable rules. The error goes to stderr, prefixed `error:` |
| `2`  | A usage error, including a `ROOT` that is not an existing directory |

```text
error: invalid JSON in schema docs/__meta__/feat.structure.json: Expecting property name enclosed in double quotes
```

## Limitations

- A skill is shown as found, not as valid: `inspect` does not read a `SKILL.md`;
  [check skills](cli-check-skills.md) does.
- A skill entry that is a symlink does not show where it leads.
- A file the model [leaves out](workspace.md#left-out-not-reported), such as a Markdown file in a
  subdirectory of a corpus, is not shown at all.

## References

- [cli](cli.md) - Base: the command line and the options every command shares
- [workspace](workspace.md) - Dependency: the layout the model is read from
- [spec](spec.md) - Related: how a stem selects the corpus and the documents it governs
- [cli-check](cli-check.md) - Related: the checks that read the same model

## Code References

- `src/lorecraft/cli/commands/inspect.py` - Declares the command, loads the model
- `src/lorecraft/cli/workspace_tree.py` - Draws the tree and renders the JSON
- `src/lorecraft/project/workspace/` - The workspace model and its loader
