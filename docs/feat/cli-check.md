---
name: "cli-check"
description: "The lorecraft check command: every rule over every document and skill of the workspace, root discovery, selecting and ignoring rules by code or prefix, the rule groups and their codes, the text and JSON output, and the 0/1/2 exit status. Load when running the documentation and skill checks, wiring them into CI or a pre-commit hook, running some rules only, matching on a rule code, or parsing their output"
type: "feature"
status: "experimental"
components: "module:lorecraft.cli,module:lorecraft.engine,module:lorecraft.rules"
---

# `lorecraft check`

## Summary

Checks docs against meta specs, skills against the Agent Skills spec; broken rules/load failures are diagnostics (`FM001`), errors exit `1`.

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
- **Rule**: One judgment of a subject, with a code and kebab-case name. Its default level is `deny` or `warn`.
- **Diagnostic**: One occurrence: a path, optional line, severity, code, message, labels, help and notes.
  They sort by path, location, severity, code and message.
- **Line**: A line ends only at `\n`, at `\r\n` as one break, or at a lone `\r`. Vertical tab, form feed, U+0085,
  U+2028 and U+2029 stay within a line. Findings and source excerpts use these lines.
- **Governed**: `structure` needs a corpus structure file, `frontmatter` a schema, `outline` an applying file's outline, and `budget` a `tokens` or `lines` declaration;
  a rule over an ungoverned part does not run (coverage, not a diagnostic).
- **Frontmatter format**: The [accepted YAML subset](frontmatter.md), decoded to JSON values; `FM002` names
  refused constructs and syntax errors, while `FM005` reports repeated keys.

## Architecture

### Root Discovery

Without `--root`, the root is the nearest of the working directory and its parents holding `docs/__meta__/`.
With `--root`, the given directory must exist. The root is resolved with symlinks followed; output paths are
relative to it. `docs/` and `docs/__meta__/` must be [real directories](workspace.md#one-snapshot).

### The Subjects

Checks docs/specs, skills/resources and escaping symlinks. `LINK001`–`LINK003` check documents, meta specs and skills, even without a corpus structure file. `LINK005`–`LINK007` require the structure meta spec; `LINK005` and `LINK006` also check meta specs. Prose specs in `docs/__meta__/` are subjects in reserved `meta`; their frontmatter, outline and length rules apply. Without `meta.spec.json`, each reports `ungoverned for frontmatter, structure, outline, budget`. Subjects and diagnostics follow path order. Resources without governed parts are ungoverned.
### One Run, One Snapshot

One snapshot, meta specs first. A failed structure file yields a diagnostic. Failed layers suppress every meta-spec rule on items; package and schema rules and `Always` links still run. Suppressed parts appear as `ungoverned for ...`. `LC001` invalid UTF-8 is unjudged. Diagnostics and coverage use the actual `.spec.json` name.
### Selecting Rules

`--select` and `--ignore` take comma-separated or repeated selectors: `ALL`, a group prefix (`OUT`), a code
prefix (`OUT0`), a rule code (`OUT006`) or its alias. Selectors are case-sensitive; without `--select`, all run.

The most specific selector decides; `--ignore` wins ties.

Invalid selectors exit `2`; aliases and `allow` rules warn.

## Configuration

| Argument or option | Default | Env var | Description |
|--------------------|---------|---------|-------------|
| `--no-builtin-skills-schema` | unset | — | Do not apply the bundled Agent Skills schema or its contradiction preflight; repository schemas still apply |
| `--root <path>`    | nearest of working directory and parents holding `docs/__meta__/` | — | The repository root, as [Root Discovery](#root-discovery) describes |
| `--format <text\|short\|json>` | `text` | — | The output format, as [Output](#output) describes |
| `--color <WHEN>` | `auto` | [`NO_COLOR`](https://no-color.org/), [`FORCE_COLOR`](https://force-color.org/) | Only `text` is colored. `auto`: nonempty `FORCE_COLOR` enables even when piped; else nonempty `NO_COLOR` disables; otherwise stdout's TTY state applies. Empty is unset; any nonempty value, even `0`, is set. Explicit `always`/`never` wins. Errors bold red; warnings bold yellow; messages bold; gutter/location markers bold blue. |
| `--select <selectors>` | `ALL` | — | Run only these rules, as [Selecting Rules](#selecting-rules) describes |
| `--ignore <selectors>` | none | — | Skip these rules |

An unlisted `--format` or `--color` exits `2`. An explicit `--color always` or `--color never` wins. Under `auto`, non-empty `FORCE_COLOR` enables colour even when piped; otherwise non-empty `NO_COLOR` disables it; otherwise colour follows whether stdout is a terminal. Empty variables are unset; any non-empty value, including `0`, is set. Enabled colours: errors bold red, warnings bold yellow, messages bold, gutter and location markers bold blue.

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

`--no-builtin-skills-schema` skips the bundled schema and contradiction preflight; repository schemas still apply, so
`FM004` can run. It expects the listed directory name and never guides renaming `SKILL.md`. Without a repository
schema, skill frontmatter has no diagnostics and is ungoverned; with opt-out, it adds `ungoverned for frontmatter`
to the coverage line (exit `0`), including for malformed/missing frontmatter or mismatched names. See [The Subjects](#the-subjects)
for other ungoverned parts. Excluding required `name`/`description` fails; indirect and cross-layer constraints are unchecked.

### Output

In `text`, stdout has blank-line-separated diagnostics with severity, code, message, numbered source and labels. Reported lines underline solid; other labels dotted. Nearby lines group; distant lines use ellipses; `:::` points to another file. Help/notes use `= help:`/`= note:`. Single-line help/notes wrap to terminal width (100 piped, ignoring `COLUMNS`); multi-line breaks and lone `\r` notes stay separate.

Check output (stdout):

```text
error[OUT006]: missing required section `Checklist`
 --> docs/code/logging.md:1
  │
1 │ # Logging
  │ ───────── expected `Checklist` before the end of the document
  │
 ::: docs/__meta__/code.spec.json
  │
  = note: the document structure is set here
  = help: The items a reviewer verifies before committing a change the rule document governs.
```

On stderr, `text` prints coverage, counts per code prefix and `checked N subject(s): ...` (including unreadable specs). Refused paths appear in skipped coverage.
One subject, two errors:

```text
FM   1 error
OUT  1 error
checked 1 subject(s): 2 error(s), 0 warning(s)
```

In `short`, stdout has one diagnostic per line:
`path:line: severity[code]: message`, or `path: severity[code]: message` for a whole file. It omits
labels, help and notes; `text` order and exit status are retained. Stderr has coverage and the overall count, without prefix counts. For example:

```text
docs/code/logging.md:1: error[OUT006]: missing required section `Checklist`
```

In `json`, stdout is one compact line; stderr holds selection warnings. In text order, `diagnostics` lists `path`, nullable `line`, `severity`, `code`, `name`, `message`, `labels` and `children`. `summary` counts subjects/errors/warnings; load failures are errors, not subjects. `coverage` lists `path`, ungoverned parts and refused paths in `skipped_by`:

```json
{"diagnostics":[{"path":"docs/notes/broken.md","line":4,"severity":"error","code":"LC001","name":"invalid-utf8","message":"file is not valid UTF-8","labels":[{"path":"docs/notes/broken.md","line":4,"text":"0xE9 at byte offset 31 starts a character the next byte does not continue"}],"children":[{"kind":"help","text":"save the file as UTF-8","path":null,"line":null}]}],"summary":{"subjects":3,"errors":1,"warnings":0},"coverage":[{"path":"docs/notes/todo.md","ungoverned":["outline","budget"],"skipped_by":[]}]}
```

JSON paths must be UTF-8; non-ASCII text is direct, not escaped.

### Exit Status

| Code | Meaning |
|------|---------|
| `0`  | No diagnostic is an error; warnings and ungoverned parts do not count |
| `1`  | An error diagnostic, including a failed meta spec or unreadable `docs/` path (`LC002`) |
| `2`  | No root; unlistable `docs/` or `docs/__meta__/`; scan-blocking refusal outside `docs/` (including skill-directory/link refusals); changed snapshot entry; invalid selection or usage. Errors print to stderr; selector usage errors follow [cli](cli.md) |

## Limitations

- Rules use their default level; selection only narrows the run.
- Warnings do not fail the run: [`FM007`](../rulebook/FM007-unknown-field.md),
  [`LINK005`](../rulebook/LINK005-extension-link.md), [`LINK006`](../rulebook/LINK006-missing-base-link.md),
  [`LINK007`](../rulebook/LINK007-mutual-link.md) or [`COR001`](../rulebook/COR001-reserved-corpus-overlap.md),
  all exit 0. LINK007 puts `help` before `note`.
  `COR001` is selectable; if its level makes it an error, the run exits 1.
- A whole subject, such as a layout entry, shows `--> path` without an excerpt. Unreadable source appears as
  `= at path:line: text`. Excerpts are available for documents, `SKILL.md`, resources and meta spec
  files in `docs/__meta__/`; other paths have none.
  A UTF-8 byte order mark is omitted from excerpted line 1, so its underline spans only the visible text.
  The gutter uses `| ^ - .` without UTF-8 output.
- Skills without `docs/__meta__/` need `--root`.
- Checks cover machine decisions; review judges what a section says.

## Findings

| Rule | Reported when |
|------|---------------|
| `FM` | Frontmatter checks use applicable schemas; the bundled skills schema is optional. `FM004` compares skill names with listed directories. `FM001` missing-frontmatter, `FM002` invalid-yaml, `FM003` non-mapping-frontmatter, `FM004` name-mismatch, `FM005` duplicate-key, `FM006` missing-field, `FM007` unknown-field (a warning), `FM008` wrong-type, `FM009` invalid-value, `FM010` invalid-frontmatter, `FM011` malformed-allowed-tools (a warning; pattern whitespace stays intact), `FM012` allowed-tools-too-long (a warning over 500 characters), `FM013` too-many-fields (`maxProperties`, an error), `FM014` too-few-fields (`minProperties`, an error) |
| `OUT` | Outline checks: a document's H1 title and sections against its structure files. `OUT001` missing-title, `OUT002` extra-title, `OUT003` title-not-first, `OUT004` empty-section, `OUT005` forbidden-section, `OUT006` missing-section, `OUT007` section-out-of-order, `OUT008` unexpected-section, `OUT009` invalid-title |
| `LEN` | Length limits: a document's tokens or declared lines budget, a section's or its title's words or characters, and a `SKILL.md`'s default lines limit. `LEN001` too-many-tokens, `LEN002` too-many-lines, `LEN003` section-too-many-words, `LEN004` title-too-many-words, `LEN005` title-too-long |
| `LINK` | Links in structured documents and skills. `LINK001` absolute, `LINK002` broken fragment, `LINK003` broken, `LINK004` escaping, `LINK005` extension-link (link to same-directory name extension; warning; also checks meta specs), `LINK006` missing-base-link (an extension omits its nearest existing document or meta spec ancestor under `References`; warning; also checks meta specs), `LINK007` mutual-link (documents in different corpora link each other; warning) |
| `COR` | Corpus layout checks: `COR001` reserved-corpus-overlap, a directory under `docs/` has a reserved corpus name such as `skills`; warning by default. It can be selected or ignored by code or group. |
| `LAY` | Skill layout checks: `LAY001` escaping-symlink, a symlink an agent reaches whose chain leaves the repository |
| `LC` | Engine conditions are errors with no level; selection and configuration cannot turn them off. `LC001` invalid-utf8 reports a file that cannot be decoded, including a structure file; `LC002` unreadable-path reports a workspace path the run cannot read, list or follow; `LC003` malformed-structure-file reports a structure file that breaks the format or states no rule; `LC004` unusable-structure-file reports a well-formed structure file with rules that repeat, contradict each other or cannot be applied. |

`LINK005`–`LINK007` check the reference direction stated in [spec](spec.md#references-point-to-the-base).

Each reported structure-file failure appears once at that file.
`LC001` points to the first invalid byte; `LC002`, `LC003` and `LC004` are whole-file diagnostics that give
their help before their notes.
`LC002` covers unreadable paths, unknown files and unlistable nested directories.
Unreadable meta spec files and documents get an unreadable-path diagnostic and count as subjects; unknown paths do
not. Coverage skips and counts resource or `SKILL.md`
aliases at their paths, naming the refused target; `LC002` stays at target. Sibling resources and unaffected subjects
continue; all formats exit 1. A directory alias is reported at its path, never at the skill's `SKILL.md`.
Refusals outside `docs/` (including skill-directory and skill-link refusals) exit 2.

`FM008` ends with the field's example when the schema gives one. `FM009` labels malformed skill names with
their pattern. `FM010` reports other whole-block constraints with one message and no label; its note gives the
validator's wording. `FM012` to `FM014` and the `LEN` rules label the amount past the limit.

## References

- [cli](cli.md) - Base: the command line and the options every command shares
- [workspace](workspace.md) - Dependency: the documents, skills and snapshot the command reads
- [spec](spec.md#references-point-to-the-base) - Dependency: the meta spec files the rules read and their reference direction
- [frontmatter](frontmatter.md) - Related: the values the block accepts and the `FM002` and `FM005` findings
- [cli-inspect](cli-inspect.md) - Related: shows the subjects this command checks
- [cli-rule](cli-rule.md) - Related: prints the page of a rule by the code a diagnostic prints

## Code References

- `src/lorecraft/cli/commands/check.py` - Command and selectors
- `src/lorecraft/cli/check_run.py` - Rule run and exit status
- `src/lorecraft/cli/root.py` - Root discovery
- `src/lorecraft/cli/subjects.py` - Subject selection
- `src/lorecraft/cli/rule_arguments.py` - Selector validation
- `src/lorecraft/cli/rule_selection.py` - Selection and warnings
- `src/lorecraft/cli/diagnostics.py` - Short/JSON output, coverage and summaries
- `src/lorecraft/cli/diagnostic_text.py` - Full text renderer
- `src/lorecraft/cli/sources.py` - Source lines
- `src/lorecraft/cli/terminal.py` - Text style
- `src/lorecraft/cli/output.py` - Output and color choices
- `src/lorecraft/engine/skip.py` - Rules over subjects
- `src/lorecraft/rules/table.py` - Enabled rules and severity
- `src/lorecraft/rules/selection.py` - Rule filtering
- `src/lorecraft/rules/` - The rules, one module each, in a package per group
