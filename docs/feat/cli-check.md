---
name: "cli-check"
description: "The lorecraft check command group and a bare lorecraft check: repository root discovery, document selection, the text and JSON output every check prints, and the 0/1/2 exit status. Load when running the documentation or skill checks, wiring them into CI or a pre-commit hook, or parsing their output"
type: "feature"
status: "experimental"
components: "module:lorecraft.cli.commands.check,module:lorecraft.cli.check_run,module:lorecraft.cli.root,module:lorecraft.cli.select,module:lorecraft.checks.run,module:lorecraft.checks.reporting"
---

# `lorecraft check`

## Summary

`lorecraft check` validates the documents under a repository's `docs/` against the specifications in its
`docs/__meta__/`, and its agent skills against the Agent Skills specification. Named with a check, such as
`lorecraft check frontmatter`, it runs that one check; bare, it runs every check the command line carries, the
document checks over the same documents and [the skill check](cli-check-skills.md) over every skill, and prints
their findings together. Every check shares the root discovery, output formats and exit status documented here.

## Table of Contents

1. [Key Concepts](#key-concepts)
2. [Architecture](#architecture)
3. [Configuration](#configuration)
4. [Usage](#usage)
5. [Limitations](#limitations)
6. [References](#references)
7. [Code References](#code-references)

## Key Concepts

- **Check**: One subcommand of the group, validating one part of a document against the
  `<stem>.structure.json` structure specifications its path selects.
- **Finding**: One broken rule, located: a root-relative path, a line, a rule identifier and a message, and optionally
  notes that help fix it.
- **Governed**: A document is governed by a check when its corpus specification has a structure file and at
  least one structure file that applies to it states what the check reads. The structure check reads any
  file, so one stating only `tokens` or `frontmatter` governs the outline with no rule to hold it to. The
  frontmatter check asks more: the corpus file must state `frontmatter` itself. An ungoverned document is
  listed, never failed.
- **Workspace**: The root, its corpora and their documents, read once from one snapshot, as
  [workspace](workspace.md) lays out.

## Architecture

### Root Discovery

Without `--root`, the root is the nearest of the working directory and its parents that holds a
`docs/__meta__/` directory, as the [workspace layout](workspace.md#the-layout) places it. With `--root`, the given directory is the root, and it must exist. Either way it is
resolved with symlinks followed, and every path printed is relative to it.

Under the root, `docs/` and `docs/__meta__/` must be
[real directories](workspace.md#one-snapshot): a root where either is a symlink is refused by every run that
reads documents, however it was found.

### Document Selection

A bare `lorecraft check` checks every document of the [workspace](workspace.md#documents), and every skill. A
named document check does the same when given no paths. Given paths, it checks exactly those, and refuses the run when one is not such a
document — outside `docs/`, inside `docs/__meta__/`, not Markdown, in a directory no specification names, or in
a subdirectory of a corpus. Paths are relative to the working directory, not to the root.

Under the root a path is resolved in the [snapshot](workspace.md#one-snapshot), not on disk, so it names what
the run reads: a link the snapshot recorded is followed to its target, a link it never read is judged by its
spelling, and a path it holds no file at refuses the run. Above the root a link is followed on disk, so the root
may be reached through one.

### One Run, One Snapshot

Every check in a run reads the same [snapshot](workspace.md#one-snapshot). Every specification is loaded and
validated before any check runs, so one malformed specification file stops the whole run rather than one
document.

## Configuration

| Argument or option | Default | Description |
|--------------------|---------|-------------|
| `--root <path>`    | nearest parent holding `docs/__meta__/` | The repository root, as [Root Discovery](#root-discovery) describes |
| `--format <text\|json>` | `text` | The output format, as [Output](#output) describes |

Both options belong to the command that runs: `lorecraft check --root . frontmatter` is a usage error, and
`lorecraft check frontmatter --root .` is what is meant. Each check also takes the documents to check as paths,
which its own document tables.

## Usage

```bash
# Every check over every document
lorecraft check

# One check, over two documents, as JSON
lorecraft check structure docs/feat/cli.md docs/feat/cli-check.md --format json

# Check another repository
lorecraft check --root ../other-repo
```

### Output

In `text` format each finding is one line on stdout, `<path>:<line>: [<rule>] <message>`, and a summary goes to
stderr. A document no specification governs for the check is listed as `<path>:1: [<corpus>.ungoverned]
<reason>`, which is not a finding.

```text
docs/feat/spec-demo.md:3: [feat.description] 'A demo' does not match 'Load when' (per docs/__meta__/feat.structure.json)
docs/feat/spec-demo.md:15: [structure.empty] section `Key Concepts` is empty; omit it rather than leaving it empty (per feat.md)
docs/feat/spec-demo.md:15: [structure.outline] expected section `Table of Contents`, found `Key Concepts` (per feat.md)
checked 1 file(s) and 16 skill(s) with 4 check(s), 3 finding(s)
```

A check may attach notes to a finding, each a `help` or a `note`. In text they follow the finding line, indented
as `  = help: <text>` or `  = note: <text>`, with a multi-line text aligned under its first line. A note is not
part of the message.

```text
docs/feat/spec-demo.md:1: [structure.outline] missing required section `Key Concepts` (per feat.md)
  = help: The terms the document uses, defined once, in one line each; a term the whole toolkit uses is linked to the glossary instead of defined again.
  = note: for example:
          ## Key Concepts

          - **Root**: The directory that holds `docs/__meta__/`; every path lorecraft prints is relative to it.
          - **Corpus**: A directory directly under `docs/` whose documents specifications govern, named by the
            directory.
          - **Document**: A Markdown file directly inside a corpus directory.
          - **Workspace model**: The corpora, their specifications and their documents, as found in one snapshot.
```

A named check counts only what it checks: `checked 1 file(s), 1 finding(s)`, or `checked 16 skill(s), 0
finding(s)` for the skill check.

In `json` format stdout is one JSON object and stderr is empty. A named check prints its report; a bare run
prints every report under `checks`, keyed by check name, the skill check's among them. `spec` is the root-relative specification file
stating the rule, or `null` for a rule the check holds itself. `notes` lists the finding's notes as `{"kind",
"text"}` objects, and is empty when there are none. `lorecraft check frontmatter --format json`:

```json
{"checked": 1, "findings": [{"file": "docs/feat/spec-demo.md", "line": 3, "rule": "feat.description", "message": "'A demo' does not match 'Load when' (per docs/__meta__/feat.structure.json)", "spec": "docs/__meta__/feat.structure.json", "notes": []}], "ungoverned": []}
```

### Exit Status

| Code | Meaning |
|------|---------|
| `0`  | No check reported a finding; ungoverned documents do not count |
| `1`  | At least one finding |
| `2`  | The run could not start: no root, a symlinked `docs/` or `docs/__meta__/`, a rejected path, an unreadable file, a malformed specification, or a usage error. Only the error is printed, on stderr, prefixed `error:` and followed by its causes ([cli](cli.md)) |

## Limitations

- A bare `lorecraft check` takes no paths: it always checks every document and every skill.
- A check covers what a machine can decide. Whether a section says what it should stays with review.

## References

- [cli](cli.md) - Base: the command line and the options every command shares
- [workspace](workspace.md) - Dependency: the corpora and documents the checks select
- [spec](spec.md) - Dependency: the specification files the checks read
- [cli-check-skills](cli-check-skills.md) - Related: the check over agent skills, which a bare run includes

## Code References

- `src/lorecraft/cli/commands/check/__init__.py` - The group and the bare run
- `src/lorecraft/cli/check_run.py` - Check registration, selection and both output formats
- `src/lorecraft/cli/root.py` - Root discovery
- `src/lorecraft/cli/select.py` - The rules a path argument is refused by
- `src/lorecraft/checks/run.py` - A check's run over the selected documents, or skills
