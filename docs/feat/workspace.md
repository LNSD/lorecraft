---
name: "workspace"
description: "The fixed repository layout lorecraft reads: the root holding docs/__meta__/, corpus directories under docs/, the flat Markdown documents inside them, what is left out without a report, and the one snapshot every command reads. Load when laying out a repository for lorecraft, or asking why a directory or a file is not checked"
type: "meta"
status: "experimental"
components: "module:lorecraft.project"
---

# Workspace Layout

## Summary

lorecraft reads one opinionated layout, and it cannot be configured: documentation lives in `docs/`, its
meta specs in `docs/__meta__/`, and each directory beside them is a corpus of flat Markdown documents. A
repository adopts lorecraft by arranging its documentation this way; nothing else registers a corpus or a
document. What lorecraft finds in that layout is the workspace model, which every command that reads a
repository works from.

## Table of Contents

1. [Key Concepts](#key-concepts)
2. [Architecture](#architecture)
3. [Limitations](#limitations)
4. [References](#references)

## Key Concepts

- **Root**: The directory that holds `docs/__meta__/`; every path a finding or the model names is relative to
  it, the root itself is printed absolute, and a refused path argument is echoed as typed.
- **Corpus**: A directory directly under `docs/` whose documents meta specs govern, named by the
  directory. The reserved `skills` corpus is the exception: its subjects are agent skills, so it has no
  directory under `docs/`.
- **Document**: A Markdown file directly inside a corpus directory.
- **Workspace model**: The corpora, their meta specs and their documents, as found in one snapshot.
- **Skills corpus**: The reserved `skills` corpus loads the meta spec files at `docs/__meta__/skills.*` and
  checks those files as meta specs. It does not govern skills or resources; the corpus
  remains separate from skills until LORE-324. It has no `docs/skills/` directory. Skills are not documents.
- **Overlapping corpus**: A `docs/skills/` directory is ignored, including its documents. The model records this name overlap, and `lorecraft check` reports it as the
  [`COR001` warning](../rulebook/COR001-reserved-corpus-overlap.md). Skills retain their `Always` checks, and resources retain `Always` Markdown checks; neither receives corpus governance. Skill specs do
  not change which rules check a `SKILL.md`.

## Architecture

### The Layout

```text
<root>/
└── docs/
    ├── __meta__/            meta specs: <name>.md and <name>.spec.json files
    ├── feat/                a corpus, governed by docs/__meta__/feat.*
    │   ├── cli.md           a document
    │   └── cli-check.md     a document
    ├── schemas/             no docs/__meta__/schemas.* file, so not a corpus
    └── glossary.md          not inside a corpus, so not a document
```

### Corpora

A directory directly under `docs/` is a corpus when it is a real directory, not a symlink, and at least one
meta spec file in `docs/__meta__/` sits at its name. A corpus name is lowercase letters, digits and
underscores, starting with a letter or an underscore: `docs/cli_specs/`, never `docs/cli-specs/`, since a
hyphen in a meta spec's name separates the corpus from a namespace. `docs/__meta__/` is never a corpus.
How the meta spec files are named and layered is [spec](spec.md)'s subject.

### Documents

A document is a regular Markdown file directly inside a corpus, named in lowercase letters and digits, with
single hyphens or underscores, starting with a letter. The hierarchy between documents is in their names, not
in directories: a corpus is flat.

### Left Out, Not Reported

What the layout does not place is not part of the model, and lorecraft passes over it silently: a directory
under `docs/` that no meta spec names, a Markdown file at `docs/` itself or in a subdirectory of a corpus,
a symlinked file or corpus directory, and a file whose name does not parse. Only a path named on the command
line is refused with a reason, since it was asked for.

### One Snapshot

A command reads `docs/` and the directories directly in it once, at start, and works from that copy: one moment
of the tree, even while files change. It reads each agent's skills directory, such as `.agents/skills/`, each skill
directory in it, and every file and directory inside a skill, at any depth. That is the scope, and it is declared: a
directory it names is in it even when absent, so a file missing there is missing. Under `docs/` a symlink is recorded, not followed: a path through
one is in the scope only when it leads where the scope reads anyway. Under a skills directory, and inside a skill, a
symlink into the repository is followed, to a directory at any depth and to a file for its contents; one leading
outside the repository is not, and [check](cli-check.md) reports it. The model records where each skill's
directory and `SKILL.md` lead.

`docs/` and `docs/__meta__/` themselves must be real directories. Behind a symlink the snapshot would hold no
meta spec, so a command stops with an error naming the linked directory rather than read an empty model.

## Limitations

- The layout is fixed: `docs/` and `docs/__meta__/` cannot be renamed or moved, and a corpus cannot nest.
- The snapshot reads the whole of a skill, but [check](cli-check.md) checks only its Markdown files: the
  `SKILL.md`'s frontmatter and length, and the links in every Markdown file of the skill. Its other files are
  read, not checked.
- A skill link can read a large subtree, including an ancestor; each directory is read once. A link into `docs/`
  follows its symlinks. For `check`, an unlistable or unresolvable skills directory or entry, or an unresolvable
  `SKILL.md` link, gives `LC002`. An unlistable directory inside a skill that no load failure reports exits `2`.
- An entry that changes kind while the snapshot is read, such as a directory replaced by a symlink, stops the
  command with an error naming it. Running it again reads the tree as it then stands.
- An unlistable directory under `docs/` that no meta spec names stops `check` with exit `2` and
  `cannot snapshot directory <path>: permission denied`.
- An entry on a followed link chain that the run cannot inspect also exits `2` when no load failure reports it.

## References

- [spec](spec.md) - Related: the meta spec files in `docs/__meta__/` and how they govern documents
- [cli](cli.md) - Related: the command line that reads the workspace
