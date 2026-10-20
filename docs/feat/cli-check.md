---
name: "cli-check"
description: "The lorecraft check command: every rule over every document and skill of the workspace, root discovery, selecting and ignoring rules by code or prefix, the rule groups and their codes, the text and JSON output, and the 0/1/2 exit status. Load when running the documentation and skill checks, wiring them into CI or a pre-commit hook, running some rules only, matching on a rule code, or parsing their output"
type: "feature"
status: "experimental"
components: "module:lorecraft.cli,module:lorecraft.engine,module:lorecraft.rules"
---

# `lorecraft check`

## Summary

Checks docs against specs and skills against the Agent Skills spec; load failures are diagnostics, refused item reads are `LC002`, errors exit `1`.

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

- **Subject**: A document, skill `SKILL.md`, Markdown skill resource, or skill-layout symlink leading outside the repository.
- **Rule**: A judgment of a subject with a code, kebab-case name and default level (`deny` or `warn`).
- **Diagnostic**: An occurrence with path, optional line, severity, code, message, labels, help and notes; sorted by path and location, then severity, code and message.
- **Line**: Lines end at `\n`, `\r\n` or lone `\r`; findings and excerpts use these breaks.
- **Governed**: `structure` needs a corpus structure file, `frontmatter` a schema, `outline`/`budget` an applying file's outline/`tokens`;
  Ungoverned parts appear in coverage, not diagnostics.
- **Frontmatter format**: The [accepted YAML subset](frontmatter.md), decoded to JSON values; `FM002` names refused
  constructs and syntax errors, while `FM005` reports repeated keys.

## Architecture

### Root Discovery

Without `--root`, the root is the nearest of the working directory and its parents holding `docs/__meta__/`.
With `--root`, the given directory must exist. The root resolves symlinks; output paths are
relative to it. `docs/` and `docs/__meta__/` must be [real directories](workspace.md#one-snapshot).

### The Subjects

Checks docs/specs, skills/resources and escaping symlinks. `LINK001`–`LINK003` check documents, specs and skills without a corpus structure file. `LINK004` reports a relative link climbing above its link base: repository root for documents and specs, skill root for skills and resources. Links within that bound are not escaping. `LINK005`–`LINK007` require the structure spec; `LINK005` and `LINK006` also check specs. Prose specs in `docs/__meta__/` are subjects in reserved `meta`; frontmatter, outline and length rules apply. Without `meta.spec.json`, each reports `ungoverned for frontmatter, structure, outline, budget`. Subjects and diagnostics follow path order. Ungoverned resources are reported as such.
### One Run, One Snapshot

One snapshot, specs first. A failed structure file yields a diagnostic. Failed layers suppress spec gates; `Always`, schema and link gates still run. Suppressed parts appear as `ungoverned for ...`. `LC001` invalid UTF-8 is unjudged. Diagnostics and coverage use the actual `.spec.json` name.
### Selecting Rules

`--select` and `--ignore` take comma-separated or repeated selectors: `ALL`, a group prefix (`OUT`), code
prefix (`OUT0`), rule code (`OUT006`) or alias. Selectors are case-sensitive; without `--select`, all run.

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
`FM004` can run. It expects the listed directory name and never guides renaming `SKILL.md`. Without repository
schema, skill frontmatter has no diagnostics; with opt-out, coverage says `ungoverned for frontmatter` (exit `0`),
even for malformed/missing frontmatter or mismatched names. See [The Subjects](#the-subjects). Excluding required
`name`/`description` fails; indirect and cross-layer constraints are unchecked.

### Output

In `text`, stdout has blank-line-separated diagnostics with severity, code, message, numbered source and labels. Reported lines underline solid; other labels dotted. Nearby lines group, distant lines use ellipses; `:::` points to another file. Help/notes use `= help:`/`= note:`. Single-line help/notes wrap at 100 columns when piped; multiline breaks and lone `\r` notes stay separate.

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

On stderr, `text` prints coverage, counts per code prefix and `checked N subject(s): ...` (including unreadable specs). Coverage marks an item whose own read was refused as `skipped, read refused at: <path>`; a subject blocked by a refused docs dependency is `skipped, depends on a refused docs path: <path>`. Refused reads of documents, specs, skill entrypoints and Markdown resources produce `LC002`. Other refused skill files remain scan-blocking errors and exit `2`. Symlinked corpora and `.md` entries appear as `path: not checked (symlink)`; links are not followed, diagnosed or counted.
Example: one subject, two errors.

```text
FM   1 error
OUT  1 error
checked 1 subject(s): 2 error(s), 0 warning(s)
```

In `short`, stdout has one diagnostic per line:
`path:line: severity[code]: message`, or `path: severity[code]: message` for a whole file. It omits
labels, help and notes; `text` order and exit status are retained. Stderr has coverage and the overall count. For example:

```text
docs/code/logging.md:1: error[OUT006]: missing required section `Checklist`
```

In `json`, stdout is one compact line; stderr holds selection warnings. In text order, `diagnostics` lists `path`, nullable `line`, `severity`, `code`, `name`, `message`, `labels` and `children`. `summary` counts subjects/errors/warnings; load failures are errors, not subjects. `coverage` lists `path`, `ungoverned`, `cause` and refused paths in `skipped_by`. `cause` is `refused-path` when the subject's own read was refused, `refused-dependency` when a refused docs path blocks it, and `null` when it was checked; unchecked symlinks add `unchecked: true`:

```json
{"diagnostics":[{"path":"docs/notes/broken.md","line":4,"severity":"error","code":"LC001","name":"invalid-utf8","message":"file is not valid UTF-8","labels":[{"path":"docs/notes/broken.md","line":4,"text":"0xE9 at byte offset 31 starts a character the next byte does not continue"}],"children":[{"kind":"help","text":"save the file as UTF-8","path":null,"line":null}]}],"summary":{"subjects":3,"errors":1,"warnings":0},"coverage":[{"path":"docs/notes/todo.md","ungoverned":["outline","budget"],"cause":null,"skipped_by":[]},{"path":"docs/code/guide.md","ungoverned":[],"cause":"refused-path","skipped_by":["docs/code/guide.md"]},{"path":"docs/code/linked.md","ungoverned":[],"cause":null,"skipped_by":[],"unchecked":true}]}
```

JSON paths must be UTF-8; Unicode is unescaped.

### Exit Status

| Code | Meaning |
|------|---------|
| `0`  | No diagnostic is an error; warnings and ungoverned parts do not count |
| `1`  | An error diagnostic, including a failed spec or unreadable `docs/` path (`LC002`) |
| `2`  | No root; unlistable `docs/` or `docs/__meta__/`; scan-blocking refusal outside reported item reads; changed snapshot entry; invalid selection or usage. A refused non-item file inside a skill scan reports `error: cannot snapshot file <path>: permission denied` without a `caused by:` line or absolute path. Errors print to stderr; selector usage errors follow [cli](cli.md) |

## Limitations

- Rules use default levels; selection only narrows the run.
- Warnings do not fail the run: [`FM007`](../rulebook/FM007-unknown-field.md),
  [`LINK005`](../rulebook/LINK005-extension-link.md), [`LINK006`](../rulebook/LINK006-missing-base-link.md),
  [`LINK007`](../rulebook/LINK007-mutual-link.md) or [`COR001`](../rulebook/COR001-reserved-corpus-overlap.md),
  all exit 0. LINK007 puts help before note.
  `COR001` is selectable; if its level makes it an error, the run exits 1.
- A whole subject shows `--> path` without an excerpt. Unreadable source appears as `= at path:line: text`;
  excerpts cover documents, skills, resources and specs. A BOM is omitted from excerpted line 1.
- Skills without `docs/__meta__/` need `--root`.
- Checks cover machine decisions; review judges what a section says.

## Findings

| Rule | Reported when |
|------|---------------|
| `FM` | Frontmatter checks use applicable schemas; the bundled skills schema is optional. `FM004` compares skill names with listed directories. `FM001` missing-frontmatter, `FM002` invalid-yaml, `FM003` non-mapping-frontmatter, `FM004` name-mismatch, `FM005` duplicate-key, `FM006` missing-field, `FM007` unknown-field (a warning), `FM008` wrong-type, `FM009` invalid-value, `FM010` invalid-frontmatter, `FM011` malformed-allowed-tools (a warning; pattern whitespace stays intact), `FM012` allowed-tools-too-long (a warning over 500 characters), `FM013` too-many-fields (`maxProperties`, an error), `FM014` too-few-fields (`minProperties`, an error) |
| `OUT` | Outline checks: a document's H1 title and sections against its structure files. `OUT001` missing-title, `OUT002` extra-title, `OUT003` title-not-first, `OUT004` empty-section, `OUT005` forbidden-section, `OUT006` missing-section, `OUT007` section-out-of-order, `OUT008` unexpected-section, `OUT009` invalid-title |
| `LEN` | Length limits: a document's tokens or declared lines budget, a section's or its title's words or characters, and a `SKILL.md`'s default lines limit. `LEN001` too-many-tokens, `LEN002` too-many-lines, `LEN003` section-too-many-words, `LEN004` title-too-many-words, `LEN005` title-too-long |
| `LINK` | Links in structured documents and skills. `LINK001` absolute, `LINK002` broken fragment, `LINK003` broken, `LINK004` escaping, `LINK005` extension-link (link to same-directory name extension; warning; also checks specs), `LINK006` missing-base-link (an extension omits its nearest existing document or spec ancestor under `References`; warning; also checks specs), `LINK007` mutual-link (documents in different corpora link each other; warning) |
| `COR` | Corpus layout checks: `COR001` reserved-corpus-overlap, a directory under `docs/` has a reserved corpus name such as `skills`; warning by default. It can be selected or ignored by code or group. |
| `LAY` | Skill layout checks: `LAY001` escaping-symlink, a symlink an agent reaches whose chain leaves the repository |
| `LC` | Engine conditions are errors with no level; selection and configuration cannot turn them off. `LC001` invalid-utf8 reports a file that cannot be decoded, including a structure file; `LC002` unreadable-path reports a workspace path the run cannot read, list or follow; `LC003` malformed-structure-file reports a structure file that breaks the format or states no rule; `LC004` unusable-structure-file reports a well-formed structure file with rules that repeat, contradict each other or cannot be applied. |

`LINK005`–`LINK007` check reference direction in [spec](spec.md#references-point-to-the-base).

Each reported structure-file failure appears once at that file.
 `LC001` points to the first invalid byte; `LC002`–`LC004` are whole-file diagnostics with help before notes.
`LC002` covers unreadable paths, unknown files and unlistable nested directories. Unreadable specs and documents count as subjects; unknown paths do not. Resource and `SKILL.md` aliases appear in coverage at their paths, naming the refused target; `LC002` stays at the target. Sibling resources and unaffected subjects continue. A directory alias appears at its path, never at the skill's `SKILL.md`.

`FM008` ends with a schema example; `FM009` labels malformed skill names with their pattern. `FM010` reports whole-block constraints without a label; its note gives the validator's wording. `FM012`–`FM014` and `LEN` label the amount over the limit.

## References

- [cli](cli.md) - Base: the command line and the options every command shares
- [workspace](workspace.md) - Dependency: the documents, skills and snapshot the command reads
- [spec](spec.md#references-point-to-the-base) - Dependency: the spec files the rules read and their reference direction
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
