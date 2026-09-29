---
name: "feat-cli"
description: "Naming, hierarchy, option tables, output and exit status rules for feature documents about the lorecraft command line. Load when writing or reviewing docs/feat/cli.md or docs/feat/cli-*.md"
type: "meta"
scope: "global"
---

# CLI Feature Document Specification

**Applies to every feature document in `docs/feat/` named `cli.md` or `cli-*.md`.** It is a namespace layer
on [feat.md](feat.md): every rule there still holds, and this document states only what it adds.

## Table of Contents

1. [Namespace](#1-namespace)
2. [Document Hierarchy](#2-document-hierarchy)
3. [Frontmatter](#3-frontmatter)
4. [Document Structure](#4-document-structure)
5. [Content Guidelines](#5-content-guidelines)
6. [Template](#6-template)
7. [Checklist](#7-checklist)

---

## 1. Namespace

The `cli` namespace documents the `lorecraft` command line: **one document per command a user can type**.
The name is the command path in kebab-case, with `cli` standing for `lorecraft`: the application itself is
`cli.md`, `lorecraft <command>` is `cli-<command>.md`, and `lorecraft <command> <subcommand>` is
`cli-<command>-<subcommand>.md`. The name is derived from the command, so no list of commands is kept here;
`lorecraft --help` is that list.

A command's options, output and exit status belong to the command's document. A concept that is not a
command — a specification dialect, the workspace model, a corpus — is not documented in this namespace, even
when a command is how a reader meets it; it takes a document in its own domain, and the command links to it.

The machine-checkable half of this layer is [feat-cli.structure.json](feat-cli.structure.json), its
`frontmatter` key included. It is applied on its own, after the `feat` file.

---

## 2. Document Hierarchy

**The shorter name is the base; every longer name extends it.** A command's base document is its parent
command's document, which is the base [feat.md §4](feat.md#4-document-structure) defines by name:
`cli-<command>.md` is the base of every `cli-<command>-<subcommand>.md`, and `cli.md` of every
`cli-<command>.md`.

What a base documents, its extensions inherit and do not restate:

- **`cli.md` documents the application**: the global options `lorecraft` itself takes, and what holds for
  every command. It is `meta`: a bare `lorecraft` prints help and runs nothing.
- **A command group's document documents what its subcommands share** — what their common options mean, the
  output format, the exit status — once. A subcommand's document links to it with `Base` and documents only
  what it adds, such as the rules a check reports.
- **A group that runs something when invoked on its own is a `feature`**, and is still the base of its
  subcommands, with a Usage section for what the bare group does. A group that only prints help is `meta`.
- **Every other command is a `feature`.** A command is not a component, even when one module implements it.

A base never links to its extensions, and never lists them: `lorecraft <command> --help` is the inventory,
and it cannot go stale.

---

## 3. Frontmatter

`components` names the module that declares the command, under `module:lorecraft.cli` — the command module
under `lorecraft.cli.commands`, or `lorecraft.cli.app` for `cli.md` — beside the library modules the command
composes. That entry is what makes a command's document findable from the code that a change to the command
touches. The `frontmatter` key of [feat-cli.structure.json](feat-cli.structure.json) requires at least one
`module:lorecraft.cli` entry; which one is right is verified by reading.

---

## 4. Document Structure

[feat.md §4](feat.md#4-document-structure) fixes the outline. This layer adds one required section and fixes
what three others hold: Usage, Findings and Code References.

### Configuration Is Required

Every command takes an argument or an option, so every document in the namespace carries a **Configuration**
section, which [feat-cli.structure.json](feat-cli.structure.json) enforces. It holds the command's arguments
and options as one table, in the order `lorecraft <command> --help` prints them:

```markdown
| Argument or option | Default | Description |
|--------------------|---------|-------------|
| `PATHS...`         | every document | Markdown files to check |
| `--format`         | `text`  | Output format: `text` or `json` |
```

- Leave out `--help`, which every command takes.
- Add an `Env var` column only when the command reads an environment variable, and state the precedence
  between the sources below the table when one value can come from more than one.
- A subcommand's table lists every argument and option it takes, as its `--help` does, since a reader
  scripting against one command reads one table. What an option means, when the base already documents
  it, is a one-line row that links to the base, not a second explanation.

### Usage Carries Output and Exit Status

A `feature` document's Usage section shows direct invocations, then two subsections a reader scripts against:

- **`### Output`** — what goes to stdout and what to stderr, in each output format, with an example of each.
- **`### Exit Status`** — a `| Code | Meaning |` table covering every code the command can return.

A subcommand whose output and exit status are its base's links to the base's subsections rather than
restating them, and documents only a difference. The structure check does not see subsections, so review
checks both.

### Findings

A command whose output carries identifiers a reader matches on, such as a check's rule identifiers, lists
them in a section of its own named **Findings**, as a `| Rule | Reported when |` table. It is a section the
document invents, so it sits after Limitations and before References.

### Code References

Name the command module under `src/lorecraft/cli/` first, then the library modules it
composes, one entry per line, never wrapped. As everywhere in the corpus, name the files and do not narrate
them.

---

## 5. Content Guidelines

- **Invoke the installed command.** Write `lorecraft check frontmatter` in examples. The CLI overview may mention
  `uv tool run lorecraft` and its `uvx lorecraft` alias for on-demand use, or `uv run lorecraft` when the
  current uv project declares Lorecraft as a dependency. Do not use a `just` recipe that wraps the command:
  the document describes the interface a user runs.
- **Agree with `--help`.** A description that says something different from the command's help text is a
  defect in one of the two; fix it in the same change.
- **Document the command as it ships.** No planned subcommand, no option the command does not take, and no
  exit code it cannot return.
- **Show real output.** An example of output is copied from a run, with only machine-specific paths
  shortened.
- **Keep the command's behaviour and the concept's apart.** How a check reads a specification is the
  specification's document; the check's document says which specification it reads and links there.

---

## 6. Template

The template adds to [feat.md §7](feat.md#7-template); the sections it does not show are as written there.

````markdown
---
name: "cli-{{command}}-{{subcommand}}"
description: "{{What the command does, its options and output. Load when [running or scripting it]}}"
type: "{{feature|meta}}"
status: "{{stable|experimental|unstable|development}}"
components: "module:lorecraft.cli.commands.{{command}},{{prefix:name - the library modules it composes}}"
---

# {{`lorecraft command subcommand`}}

## Summary

## Table of Contents

## Key Concepts

## Configuration

| Argument or option | Default | Description |
|--------------------|---------|-------------|
| `{{--option}}`     | {{default}} | {{What it controls}} |

## Usage

```bash
lorecraft {{command}} {{subcommand}}
```

### Output

{{stdout and stderr, in each format, with an example of each; or a link to the base's Output section}}

### Exit Status

| Code | Meaning |
|------|---------|
| `0`  | {{Success}} |

## Findings

| Rule | Reported when |
|------|---------------|
| `{{rule.id}}` | {{The condition}} |

## References

- [cli-{{command}}](cli-{{command}}.md) - Base: {{the parent command}}

## Code References

- `src/lorecraft/cli/commands/{{command}}.py` - Declares the command and its options
````

---

## 7. Checklist

- [ ] The name is `cli`, or `cli-` followed by the command path in kebab-case
- [ ] The document covers one command, and a concept that is not a command has its own document
- [ ] `type` is `meta` only for a command that runs nothing itself; every other command is a `feature`
- [ ] The document links to its base, the parent command's document, with `Base`, and does not link to or
      list its subcommands
- [ ] What the base documents is linked, not restated
- [ ] `components` holds the `module:lorecraft.cli` module that declares the command
- [ ] A Configuration section tables every argument and option but `--help`, in `--help` order
- [ ] A `feature` document's Usage has `### Output` and `### Exit Status`, or links to its base's
- [ ] Every exit code the command can return is in the Exit Status table
- [ ] A command reporting rule identifiers lists them under Findings
- [ ] Examples invoke `lorecraft` directly; the CLI overview gives the on-demand and conditional uv project
      alternatives, and output shown is copied from a run
- [ ] The document agrees with the command's `--help`
