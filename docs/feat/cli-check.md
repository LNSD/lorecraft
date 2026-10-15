---
name: "cli-check"
description: "The lorecraft check command: every rule over every document and skill of the workspace, root discovery, selecting and ignoring rules by code or prefix, the rule groups and their codes, the text and JSON output, and the 0/1/2 exit status. Load when running the documentation and skill checks, wiring them into CI or a pre-commit hook, running some rules only, matching on a rule code, or parsing their output"
type: "feature"
status: "experimental"
components: "module:lorecraft.cli,module:lorecraft.engine,module:lorecraft.rules"
---

# `lorecraft check`

## Summary

`lorecraft check` checks documents against their meta specs and agent skills against the Agent Skills
specification. It reports broken rules and load failures as diagnostics with codes such as `FM001`,
and exits `1` when any diagnostic is an error.

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
- **Rule**: One judgment of a subject, with a code, `<prefix><digits>`, and a kebab-case name. Its default
  level is `deny` for an error or `warn` for a warning.
- **Diagnostic**: One occurrence: a path, optional line, severity, code, message, labels, help and notes.
  Diagnostics sort by path, location, severity, code and message.
- **Line**: A line ends only at `\n`, at `\r\n` as one break, or at a lone `\r`. Vertical tab, form feed, U+0085,
  U+2028 and U+2029 stay within a line. Findings and source excerpts use these lines.
- **Governed**: A document's `structure` is governed when its corpus has a structure file, its `frontmatter` when
  that file states a schema, its `outline` or `budget` when an applying file states an outline or `tokens`. A rule
  over an ungoverned part does not run; the part is reported as coverage, not a diagnostic.
- **Frontmatter format**: The [accepted YAML subset](frontmatter.md), decoded to JSON values; `FM002` names
  refused constructs and syntax errors, while `FM005` reports repeated keys.

## Architecture

### Root Discovery

Without `--root`, the root is the nearest of the working directory and its parents holding `docs/__meta__/`.
With `--root`, the given directory must exist. The root is resolved with symlinks followed; output paths are
relative to it. `docs/` and `docs/__meta__/` must be [real directories](workspace.md#one-snapshot).

### The Subjects

A run checks every [workspace](workspace.md) document, skill, skill resource and skill-layout symlink leading
outside the repository. Shared skills are checked once. Subjects and diagnostics follow path order.

### One Run, One Snapshot

Every rule reads one [snapshot](workspace.md#one-snapshot). Meta specs load before subjects. A failed structure
file gets a diagnostic; documents it governs are skipped while others are checked. Invalid UTF-8 is `LC001`;
no rule judges that file.
A structure file's diagnostic and coverage path use its actual name, `.spec.json` or the legacy
`.structure.json`.

### Selecting Rules

`--select` and `--ignore` take selectors, comma-separated or repeated, as ruff's rule selection does. From the least
specific to the most, one is `ALL`; a group's prefix, such as `OUT`; a code prefix of one or two digits, such as
`OUT0`, every rule whose code starts with it; or a code, such as `OUT006`, or an alias code for it.
Selectors are case-sensitive; without `--select`, all rules run.

For each rule, the most specific matching selector decides, with `--ignore` winning a tie. A selection cannot
turn on a rule at `allow`.

Selectors are checked before the workspace loads. Empty, malformed, unknown, name, engine condition (`LC`
included) and removed-rule selectors exit `2`. Aliases and `allow` rules warn.

## Configuration

| Argument or option | Default | Env var | Description |
|--------------------|---------|---------|-------------|
| `--root <path>`    | nearest of working directory and parents holding `docs/__meta__/` | — | The repository root, as [Root Discovery](#root-discovery) describes |
| `--format <text\|short\|json>` | `text` | — | The output format, as [Output](#output) describes |
| `--color <WHEN>` | `auto` | [`NO_COLOR`](https://no-color.org/), [`FORCE_COLOR`](https://force-color.org/) | Control when colored output is used. `auto`: colour when stdout is an interactive terminal, unless `NO_COLOR` is set; `FORCE_COLOR` forces it. `always`: colour even when stdout is not a terminal. `never`: no colour. Only the `text` format is coloured. |
| `--select <selectors>` | `ALL` | — | Run only these rules, as [Selecting Rules](#selecting-rules) describes |
| `--ignore <selectors>` | none | — | Skip these rules |

An unlisted `--format` or `--color` value exits `2`.
For colour, an explicit `--color always` or `--color never` wins over both variables. Under `auto`, a non-empty
`FORCE_COLOR` enables colour, even when piped; otherwise a non-empty `NO_COLOR` disables it; otherwise colour
follows whether stdout is an interactive terminal. An empty variable counts as unset; any non-empty value,
including `0`, counts as set. When colour is enabled, errors are bold red, warnings bold yellow, messages bold,
and the gutter and location markers bold blue.

## Usage

```bash
lorecraft check

lorecraft check --root ../other-repo --format json

lorecraft check --format short

lorecraft check --select FM,LEN003
lorecraft check --ignore LINK

lorecraft check --select OUT006 --ignore OUT
lorecraft check --select OUT00
```

### Output

In the default `text` format, diagnostics go to stdout, separated by blank lines. A header gives severity,
code and message; numbered source lines and labels follow. The reported line has a solid underline; another
labelled line has a dotted one. Nearby lines are grouped, with an ellipsis between distant lines. `:::`
points to another file. Help and notes follow as `= help:` and `= note:`. Single-line help and notes wrap
to terminal width, or 100 columns when piped; piped output ignores `COLUMNS`. Multi-line text keeps its
line breaks. A note with a lone `\r` is drawn on separate lines under this policy.

This excerpt is from a check run (stdout):

```text
error[OUT006]: missing required section `Checklist`
 --> docs/code/logging.md:1
  │
1 │ # Logging
  │ ───────── expected `Checklist` before the end of the document
  │
 ::: docs/__meta__/code.structure.json
  │
  = note: the document structure is set here
  = help: The items a reviewer verifies before committing a change the rule document governs.
```

On stderr, `text` prints ungoverned and skipped coverage in path order, then counts per code prefix and an
overall `checked N subject(s): ...` line. Skipped coverage names each failed structure file, corpus first.
A run with one subject and two errors prints:

```text
FM   1 error
OUT  1 error
checked 1 subject(s): 2 error(s), 0 warning(s)
```

A skipped document is listed as coverage, with no rule diagnostic:

```text
docs/code/python-typing.md: skipped, governed by a structure file that failed to load: docs/__meta__/code-python.spec.json
```

In `short` format, stdout has one uncoloured line per diagnostic:
`path:line: severity[code]: message`, or `path: severity[code]: message` for a whole file. It omits
labels, help and notes, and keeps `text` order and exit status. Stderr has coverage and the overall count,
without prefix counts. For example:

```text
docs/code/logging.md:1: error[OUT006]: missing required section `Checklist`
```

In `json` format stdout is one compact JSON object on one line, without indentation or spaces after
commas or colons; stderr holds nothing but the selection's warnings. `diagnostics`
holds each diagnostic in the text order, its `line` `null` for a whole file, `labels` as `{"path", "line", "text"}`
and `children` as `{"kind", "text", "path", "line"}`, `kind` being `help` or `note`. `summary` counts the subjects,
errors and warnings; load failures count as errors but not subjects. `coverage` lists each subject with an
ungoverned part or a skipped document. Every coverage item has `path`, `ungoverned` and `skipped_by`;
`skipped_by` lists failed structure files in layer order, and `ungoverned` is empty for a skipped document:

```json
{"diagnostics":[{"path":"docs/notes/broken.md","line":4,"severity":"error","code":"LC001","name":"invalid-utf8","message":"file is not valid UTF-8","labels":[{"path":"docs/notes/broken.md","line":4,"text":"0xE9 at byte offset 31 starts a character the next byte does not continue"}],"children":[{"kind":"help","text":"save the file as UTF-8","path":null,"line":null}]}],"summary":{"subjects":3,"errors":1,"warnings":0},"coverage":[{"path":"docs/notes/todo.md","ungoverned":["outline","budget"],"skipped_by":[]}]}
```

For `--format json`, every path, including the workspace root, must be valid UTF-8. Non-ASCII text in paths,
messages, labels and notes is written as UTF-8 characters instead of `\uXXXX` escapes.

### Exit Status

| Code | Meaning |
|------|---------|
| `0`  | No diagnostic is an error; warnings and ungoverned parts do not count |
| `1`  | At least one error diagnostic, including a failed meta spec or unreadable `docs/` path (`LC002`) |
| `2`  | No root; unlistable `docs/` or `docs/__meta__/`; scan-blocking refusals outside `docs/` (including skill-directory and skill-link refusals); changed snapshot entry; invalid selection or usage. Errors print `error: ...` on stderr; selector usage errors follow [cli](cli.md) |

## Limitations

- The command takes no paths, and no option sets a level: every rule runs at its default level, and a selection
  only narrows which run.
- A warning does not fail the run: a rule whose default level is `warn`, such as
  [`FM007`](../rulebook/FM007-unknown-field.md), exits 0.
- A whole subject, such as a layout entry, shows `--> path` without an excerpt. When source text cannot be
  read, a label appears as `= at path:line: text`. Source lines are available for documents, skills' `SKILL.md`
  files, skill resources and specification files directly in `docs/__meta__/`; other paths have no excerpt.
  A UTF-8 byte order mark is omitted from excerpted line 1, so its underline spans only the visible text.
  The gutter and underlines use `| ^ - .` when UTF-8 output is unavailable.
- A repository with skills and no `docs/__meta__/` needs `--root`.
- A fragment after a path, such as `guide.md#usage`, is not checked against the file it names.
- A check covers what a machine can decide. Whether a section says what it should stays with review.

## Findings

| Rule | Reported when |
|------|---------------|
| `FM` | Frontmatter checks: a document's frontmatter against its schemas, a skill's against the Agent Skills specification and Lorecraft's recommendations. `FM001` missing-frontmatter, `FM002` invalid-yaml, `FM003` non-mapping-frontmatter, `FM004` name-mismatch, `FM005` duplicate-key, `FM006` missing-field, `FM007` unknown-field (a warning), `FM008` wrong-type, `FM009` invalid-value, `FM010` invalid-frontmatter, `FM011` malformed-allowed-tools (a warning; pattern whitespace stays intact), `FM012` allowed-tools-too-long (a warning over 500 characters), `FM013` too-many-fields (`maxProperties`, an error), `FM014` too-few-fields (`minProperties`, an error) |
| `OUT` | Outline checks: a document's H1 title and sections against its structure files. `OUT001` missing-title, `OUT002` extra-title, `OUT003` title-not-first, `OUT004` empty-section, `OUT005` forbidden-section, `OUT006` missing-section, `OUT007` section-out-of-order, `OUT008` unexpected-section, `OUT009` invalid-title |
| `LEN` | Length limits: a document's tokens, a section's or its title's words or characters, a `SKILL.md`'s lines. `LEN001` too-many-tokens, `LEN002` too-many-lines, `LEN003` section-too-many-words, `LEN004` title-too-many-words, `LEN005` title-too-long |
| `LINK` | Links in Markdown files: a document governed for its structure, a `SKILL.md` and each resource, a skill's relative link read from the skill root. `LINK001` absolute-link, `LINK002` broken-fragment, `LINK003` broken-link, `LINK004` escaping-link |
| `LAY` | Skill layout checks: `LAY001` escaping-symlink, a symlink an agent reaches whose chain leaves the repository |
| `LC` | Engine conditions are errors with no level; selection and configuration cannot turn them off. `LC001` invalid-utf8 reports a file that cannot be decoded, including a structure file; `LC002` unreadable-path reports a workspace path the run cannot read, list or follow; `LC003` malformed-structure-file reports a structure file that breaks the format or states no rule; `LC004` unusable-structure-file reports a well-formed structure file with rules that repeat, contradict each other or cannot be applied. |

Each reported structure-file failure appears once at that file.
`LC001` points to the first invalid byte; `LC002`, `LC003` and `LC004` are whole-file diagnostics that give
their help before their notes.
`LC002` covers unreadable structure files and governed documents, unreadable unknown files, and unlistable nested
directories under `docs/`. It appears at the refused path; other readable documents continue to be checked. An
unreadable governed document remains a subject and adds one to the summary count. An unknown file or directory gets
a diagnostic but is not a subject. Unlistable `docs/` or `docs/__meta__/`, and scan-blocking refusals outside
`docs/` (including skill-directory and skill-link refusals), exit 2.

`FM008` ends with the field's example when the schema gives one. `FM009` labels malformed skill names with
their pattern. `FM010` reports other whole-block constraints with one message and no label; its note gives the
validator's wording. `FM012` to `FM014` and the `LEN` rules label the amount past the limit.

## References

- [cli](cli.md) - Base: the command line and the options every command shares
- [workspace](workspace.md) - Dependency: the documents, skills and snapshot the command reads
- [spec](spec.md) - Dependency: the meta spec files the rules read
- [frontmatter](frontmatter.md) - Related: the values the block accepts and the `FM002` and `FM005` findings
- [cli-inspect](cli-inspect.md) - Related: shows the subjects this command checks
- [cli-rule](cli-rule.md) - Related: prints the page of a rule by the code a diagnostic prints

## Code References

- `src/lorecraft/cli/commands/check.py` - Declares the command and parses selectors
- `src/lorecraft/cli/check_run.py` - Runs rules and sets the exit status
- `src/lorecraft/cli/root.py` - Root discovery
- `src/lorecraft/cli/subjects.py` - Selects subjects
- `src/lorecraft/cli/rule_arguments.py` - `SelectorValue.parse` validates selectors against the rule index
- `src/lorecraft/cli/rule_selection.py` - Converts selectors and reports selection warnings
- `src/lorecraft/cli/diagnostics.py` - Renders short diagnostics, JSON, coverage and summaries
- `src/lorecraft/cli/diagnostic_text.py` - Draws the full text diagnostics
- `src/lorecraft/cli/sources.py` - Reads the source lines used by the text output
- `src/lorecraft/cli/terminal.py` - Chooses text output style
- `src/lorecraft/cli/output.py` - Declares output and colour choices
- `src/lorecraft/engine/skip.py` - Runs every enabled rule over each subject
- `src/lorecraft/rules/table.py` - The rules a run enables, each with its severity
- `src/lorecraft/rules/selection.py` - The selection that filters the rule table
- `src/lorecraft/rules/` - The rules, one module each, in a package per group
