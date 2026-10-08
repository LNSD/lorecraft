---
name: "cli-check"
description: "The lorecraft check command: every rule over every document and skill of the workspace, root discovery, selecting and ignoring rules by code or prefix, the rule groups and their codes, the text and JSON output, and the 0/1/2 exit status. Load when running the documentation and skill checks, wiring them into CI or a pre-commit hook, running some rules only, matching on a rule code, or parsing their output"
type: "feature"
status: "experimental"
components: "module:lorecraft.cli,module:lorecraft.checks,module:lorecraft.rules"
---

# `lorecraft check`

## Summary

`lorecraft check` checks the whole workspace in one run: every document under `docs/` against the specifications
in `docs/__meta__/`, and every agent skill against the Agent Skills specification. Each rule has a code, such as
`FM001`, in a group named by its prefix. It prints a diagnostic per rule broken, and exits `1` when any is an error.

## Table of Contents

1. [Key Concepts](#key-concepts)
2. [Architecture](#architecture)
3. [Configuration](#configuration)
4. [Usage](#usage)
5. [Limitations](#limitations)
6. [Findings](#findings)
7. [References](#references)
8. [Code References](#code-references)

## Key Concepts

- **Subject**: What a rule judges: a document, a skill by its `SKILL.md`, a resource of a skill (any other
  Markdown file inside it), or a symlink of the skill layout leading outside the repository.
- **Rule**: One judgment of a subject, with a code, `<prefix><digits>`, and a kebab-case name, such as `FM001`
  `missing-frontmatter`. A rule is on at its default level, `deny` for an error or `warn` for a warning.
- **Diagnostic**: One occurrence of a rule: a path, a line when it has one, a severity, the code, a message, and
  labels, help and notes.
- **Governed**: A document's `structure` is governed when its corpus has a structure file, its `frontmatter` when
  that file states a schema, its `outline` or `budget` when an applying file states an outline or `tokens`. A rule
  over an ungoverned part does not run; the part is reported as coverage, not a diagnostic.
- **Basic YAML**: The YAML a frontmatter is read as, decoding to JSON's values; an anchor, an alias, a tag, a
  second document or a key that is not a string makes the block invalid.

## Architecture

### Root Discovery

Without `--root`, the root is the nearest of the working directory and its parents that holds a
`docs/__meta__/` directory, as the [workspace layout](workspace.md#the-layout) places it. With `--root`, the
given directory is the root, and it must exist. Either way it is resolved with symlinks followed, and every path
printed is relative to it. Under the root, `docs/` and `docs/__meta__/` must be
[real directories](workspace.md#one-snapshot): a root where either is a symlink is refused, however it was found.

### The Subjects

A run checks every subject of the [workspace](workspace.md): every document it lists, every skill in the agents'
skills directories, each once however many agents read it, every resource of each skill, and every symlink of the
skill layout whose chain leaves the repository, a skills directory, an entry, a `SKILL.md` or a path inside a
skill. The subjects and the diagnostics are ordered by path, compared by code point, so one revision always prints
the same output.

### One Run, One Snapshot

Every rule reads the same [snapshot](workspace.md#one-snapshot), through one database, so a file is read and
parsed once however many rules read it. Every specification is loaded and validated before any subject is checked,
so one malformed specification stops the whole run. A file that is not UTF-8 is reported as `LC001`, and no rule
judges it.

### Selecting Rules

`--select` and `--ignore` take selectors, comma-separated or repeated, as ruff's rule selection does. From the least
specific to the most, one is `ALL`; a group's prefix, such as `OUT`; a code prefix of one or two digits, such as
`OUT0`, every rule whose code starts with it; or a code, such as `OUT006`, or an alias code for it.
Selectors are case-sensitive, and no `--select` is `ALL`.

For each rule, the most specific matching selector decides, `--ignore` winning a tie: `--select OUT006 --ignore OUT`
runs `OUT006`, `--select OUT --ignore OUT006` every `OUT` rule but it, and `--select OUT --ignore OUT` none. A
selection only filters: a selected rule at `allow` stays off.

Selectors are checked before any subject; the run exits `2` on an empty selector, one no rule or group has, a code
prefix no code starts with, a rule's name, an engine condition or `LC`, always reported, or a removed rule, naming
the release that removed it and what replaced it. An alias code, and a rule selected by its code that its level
leaves off, each print a `warning:` line on stderr, and the run goes on.

## Configuration

| Argument or option | Default | Description |
|--------------------|---------|-------------|
| `--root <path>`    | nearest parent holding `docs/__meta__/` | The repository root, as [Root Discovery](#root-discovery) describes |
| `--format <text\|json>` | `text` | The output format, as [Output](#output) describes |
| `--select <selectors>` | `ALL` | Run only these rules, as [Selecting Rules](#selecting-rules) describes |
| `--ignore <selectors>` | none | Skip these rules |

The command takes no paths: it always checks the whole workspace. Between `--select` and `--ignore`, the more
specific selector wins, as [Selecting Rules](#selecting-rules) describes.

## Usage

```bash
# Every rule over the workspace around the working directory
lorecraft check

# Another repository, as JSON
lorecraft check --root ../other-repo --format json

# The frontmatter rules and one length rule; then every rule but the links
lorecraft check --select FM,LEN003
lorecraft check --ignore LINK

# One outline rule, though its group is ignored; then the outline rules numbered 001 to 009
lorecraft check --select OUT006 --ignore OUT
lorecraft check --select OUT00
```

### Output

In `text` format each diagnostic goes to stdout, an empty line between two. Its first line is
`<path>:<line>: <severity>[<code>]: <message>`, with no `:<line>` when it concerns the whole file. Each label
follows as `  --> <path>:<line>: <text>`, then each help or note as `  = help: <text>` or `  = note: <text>`, a
multi-line text aligned under its first line. On stderr, a line per subject with an ungoverned part, then a
summary:

```text
docs/code/guide.md:1: error[FM001]: no `---` delimited frontmatter block
  --> docs/code/guide.md:1: a `---` delimited block is expected here
  = note: the frontmatter schema is set here (docs/__meta__/code.structure.json)
  = help: open the file with a `---` line, the fields, and a closing `---` line

docs/code/guide.md:1: error[OUT006]: missing required section `Checklist`
  --> docs/code/guide.md:1: expected `Checklist` before the end of the document
  = note: the document structure is set here (docs/__meta__/code.structure.json)
docs/notes/todo.md: ungoverned for outline, budget
checked 2 subject(s): 2 error(s), 0 warning(s)
```

In `json` format stdout is one JSON object, and stderr holds nothing but the selection's warnings. `diagnostics`
holds each diagnostic in the text order, its `line` `null` for a whole file, `labels` as `{"path", "line", "text"}`
and `children` as `{"kind", "text", "path", "line"}`, `kind` being `help` or `note`. `summary` counts the subjects,
errors and warnings, and `coverage` lists each subject with an ungoverned part:

```json
{"diagnostics": [{"path": "docs/notes/broken.md", "line": 4, "severity": "error", "code": "LC001", "name": "invalid-utf8", "message": "file is not valid UTF-8", "labels": [{"path": "docs/notes/broken.md", "line": 4, "text": "0xE9 at byte offset 31 starts a character the next byte does not continue"}], "children": [{"kind": "help", "text": "save the file as UTF-8", "path": null, "line": null}]}], "summary": {"subjects": 3, "errors": 1, "warnings": 0}, "coverage": [{"path": "docs/notes/todo.md", "ungoverned": ["outline", "budget"]}]}
```

### Exit Status

| Code | Meaning |
|------|---------|
| `0`  | No diagnostic is an error; warnings and ungoverned parts do not count |
| `1`  | At least one diagnostic is an error, `LC001` included |
| `2`  | The run could not start: no root, a symlinked `docs/` or `docs/__meta__/`, an unreadable file, an entry that changed kind while read, a malformed specification, a selector that cannot be used, or a usage error. Only the error is printed, on stderr, as [cli](cli.md) describes |

## Limitations

- The command takes no paths, and no option sets a level: every rule runs at its default level, and a selection
  only narrows which run.
- A warning does not fail the run: a rule whose default level is `warn`, such as
  [`FM007`](../rulebook/FM007-unknown-field.md), exits 0.
- A repository with skills and no `docs/__meta__/` needs `--root`.
- A key repeated inside a nested frontmatter mapping is not reported as repeated.
- A fragment after a path, such as `guide.md#usage`, is not checked against the file it names.
- A check covers what a machine can decide. Whether a section says what it should stays with review.

## Findings

Each group is one area of the specifications. What each rule checks, why it matters and how to fix it is in its page
of the [rulebook](../rulebook/), in this repository, and `lorecraft rule <code>` anywhere, as
[cli-rule](cli-rule.md) describes.

| Rule | Reported when |
|------|---------------|
| `FM` | Frontmatter checks: a document's frontmatter against its schemas, a skill's against the Agent Skills specification and Lorecraft's recommendations. `FM001` missing-frontmatter, `FM002` invalid-yaml, `FM003` non-mapping-frontmatter, `FM004` name-mismatch, `FM005` duplicate-key, `FM006` missing-field, `FM007` unknown-field (a warning), `FM008` wrong-type, `FM009` invalid-value, `FM010` block-constraint, `FM011` malformed-allowed-tools (a warning; pattern whitespace stays intact), `FM012` allowed-tools-too-long (a warning over 500 characters) |
| `OUT` | Outline checks: a document's H1 title and sections against its structure specifications. `OUT001` missing-title, `OUT002` extra-title, `OUT003` title-not-first, `OUT004` empty-section, `OUT005` forbidden-section, `OUT006` missing-section, `OUT007` section-out-of-order, `OUT008` unexpected-section, `OUT009` invalid-title |
| `LEN` | Length limits: a document's tokens, a section's or its title's words or characters, a `SKILL.md`'s lines. `LEN001` too-many-tokens, `LEN002` too-many-lines, `LEN003` too-many-words, `LEN004` title-too-many-words, `LEN005` title-too-long |
| `LINK` | Links in Markdown files: a document governed for its structure, a `SKILL.md` and each resource, a skill's relative link read from the skill root. `LINK001` absolute-link, `LINK002` missing-fragment, `LINK003` broken-link, `LINK004` escaping-link |
| `LAY` | Skill layout checks: `LAY001` outside-symlink, a symlink an agent reaches whose chain leaves the repository |
| `LC` | Engine conditions, which no configuration or selection turns off: `LC001` invalid-utf8, a file that is not UTF-8, reported at its first invalid byte |

## References

- [cli](cli.md) - Base: the command line and the options every command shares
- [workspace](workspace.md) - Dependency: the documents, skills and snapshot the command reads
- [spec](spec.md) - Dependency: the specification files the rules read
- [cli-inspect](cli-inspect.md) - Related: shows the subjects this command checks
- [cli-rule](cli-rule.md) - Related: prints the page of a rule by the code a diagnostic prints

## Code References

- `src/lorecraft/cli/commands/check.py` - Declares the command, runs the rules and chooses the exit status
- `src/lorecraft/cli/root.py` - Root discovery
- `src/lorecraft/cli/subjects.py` - Selects every subject of the workspace, in path order
- `src/lorecraft/cli/rule_selection.py` - Parses `--select` and `--ignore` against the registry
- `src/lorecraft/cli/diagnostics.py` - Renders the diagnostics, the coverage and the summary as text or JSON
- `src/lorecraft/checks/runner.py` - Runs every enabled rule over each subject
- `src/lorecraft/checks/table.py` - The rules a run enables, each with its severity
- `src/lorecraft/checks/selection.py` - The selection that filters the rule table
- `src/lorecraft/rules/` - The rules, one module each, in a package per group
