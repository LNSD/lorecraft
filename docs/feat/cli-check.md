---
name: "cli-check"
description: "The lorecraft check command: workspace checks, root discovery, level flags, text and JSON reports, and exit status. Load when running checks, setting rule levels or interpreting reports"
type: "feature"
status: "experimental"
components: "module:lorecraft.cli,module:lorecraft.engine,module:lorecraft.rules"
---

# `lorecraft check`

## Summary

Checks enabled rules over documents and skills against applicable specifications. `-A`, `-W` and `-D` set rule levels; a specific code can override `-A ALL` to run selected rules. Refused items are skipped; non-item failures use `LC002`.

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
- **Frontmatter format**: The [accepted YAML subset](frontmatter.md), decoded to JSON values; `LC202` names refused
  constructs and syntax errors, while `LC205` reports repeated keys.

## Architecture

### Root Discovery

Without `--root`, the root is the nearest of the working directory and its parents holding `docs/__meta__/`.
With `--root`, the given directory must exist. The root resolves symlinks; output paths are
relative to it. `docs/` and `docs/__meta__/` must be [real directories](workspace.md#one-snapshot).

### The Subjects

Checks docs/specs, skills/resources and escaping symlinks. `LC501`–`LC503` check documents, specs and skills without a corpus structure file. `LC504` reports a relative link climbing above its link base: repository root for documents and specs, skill root for skills and resources. Links within that bound are not escaping. `LC505`–`LC507` require the structure spec; `LC505` and `LC506` also check specs. Prose specs in `docs/__meta__/` are subjects in reserved `meta`; frontmatter, outline and length rules apply. Without `meta.spec.json`, each reports `ungoverned for frontmatter, structure, outline, budget`. Subjects and diagnostics follow path order. Ungoverned resources are reported as such.
### One Run, One Snapshot

One snapshot, specs first. A failed structure file yields a diagnostic. Failed layers suppress spec gates; `Always`, schema and link gates still run. Suppressed parts appear as `ungoverned for ...`. `LC001` invalid UTF-8 is unjudged. Diagnostics and coverage use the actual `.spec.json` name.
Conflicting-level errors name `-A`, `-W`, `-D`; invalid values exit `2` before root discovery. Level flags apply to the rule table: full active codes and alias codes are accepted with `ALL`, and a specific code takes precedence over `ALL` regardless of argument order. Conflicting assignments for one code are usage errors. `-W` or `-D` enables a rule whose default level is `allow`; `-A` leaves it out. With `-A ALL -D <code>`, only the named rules run. `-D warnings` raises every resolved warning to an error after code overrides.

## Configuration

| Argument or option | Default | Env var | Description |
|--------------------|---------|---------|-------------|
| `--root <path>`    | nearest of working directory and parents holding `docs/__meta__/` | — | The repository root, as [Root Discovery](#root-discovery) describes |
| `--format <text\|short\|json>` | `text` | — | The output format, as [Output](#output) describes |
| `--color <WHEN>` | `auto` | [`NO_COLOR`](https://no-color.org/), [`FORCE_COLOR`](https://force-color.org/) | `text` only. `auto`: nonempty `FORCE_COLOR` enables; else nonempty `NO_COLOR` disables; otherwise stdout's TTY state applies. Empty is unset; any nonempty value, even `0`, is set. Errors red, warnings yellow, messages bold, gutters blue. |
| `-A`, `--allow <code>` | none | — | Allow a code, alias or `ALL`; repeatable |
| `-W`, `--warn <code>` | none | — | Warn on a code, alias or `ALL`; repeatable |
| `-D`, `--deny <code>` | none | — | Deny a code, alias, `ALL` or `warnings`; repeatable |

`warnings` is reserved for `-D`; using it with `-A` or `-W` exits `2` with a usage error explaining this restriction.

Unlisted `--format` or `--color` exits `2`. Explicit `always`/`never` wins; the table gives `auto` precedence.

## Usage

```bash
lorecraft check

lorecraft check --root ../other-repo --format json

lorecraft check --format short

```

With the global `--no-agent-skills-spec` ([cli](cli.md)), given before the command, the builtin Agent Skills spec and floor
are off. `LC204` compares `name` with the skill directory; it never
suggests renaming `SKILL.md`. Without a repository skills spec, opt-out reports `ungoverned for frontmatter, budget`
(exit `0`) even for malformed frontmatter or mismatched names; `LC402`, `LC211` and `LC212` do not run. Default
skill coverage omits `budget`. Excluding required `name`/`description` fails; indirect and cross-layer constraints
are unchecked. See [The Subjects](#the-subjects) and [structure budgets](spec-structure-budget.md).

### Output

In `text`, stdout has blank-line-separated diagnostics with severity, code, message, source and labels. Reported lines underline solid; other labels dotted. Nearby lines group; distant lines use ellipses; `:::` points to another file. Help/notes use `= help:`/`= note:`. Notes appear only when the effective level differs from the rule default. CLI notes preserve the typed selector, including aliases; warning elevation says `-D warnings elevated warning to error`. Configuration notes name the `warn`/`deny` level and selector.

Example (stdout):

```text
error[LC306]: missing required section `Checklist`
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

On stderr, `text` prints coverage, counts per code group and `checked N subject(s): ...`. Refused items are `skipped, read refused at: <path>`; subjects blocked by refused docs dependencies are `skipped, depends on a refused docs path: <path>`. Refused document/spec reads produce `LC002`; a refused non-item docs path keeps `LC002` even when a skill item aliases it, and that item is skipped. Other refused skill files remain scan-blocking errors and exit `2`. Symlinked corpora and `.md` entries are not checked; links are not followed or counted.

```text
LC2xx  1 error
LC3xx  1 error
checked 1 subject(s): 2 error(s), 0 warning(s)
```

In `short`, stdout has one diagnostic per line:
`path:line: severity[code]: message`, or `path: severity[code]: message` for a whole file. It omits
labels, help and notes; `text` order and exit status are retained. Stderr has coverage and the overall count. For example:

```text
docs/code/logging.md:1: error[LC306]: missing required section `Checklist`
```

In `json`, stdout is one compact line; stderr holds command warnings. In text order, `diagnostics` lists `path`, nullable `line`, `severity`, `level_source`, `code`, `name`, `message`, `labels` and `children`. `level_source` is always present: `default` when the effective level equals the rule default, `config` when a configuration level changes it, or `cli` when a command-line level changes it. `-D warnings` sets `level_source` to `cli` when it elevates a warning above its default. `summary` counts subjects and severities; load failures are errors, not subjects. `coverage` gives each path's `ungoverned`, `cause` (`refused-path`, `refused-dependency` or null) and refused paths in `skipped_by`; unchecked symlinks add `unchecked: true`:

```json
{"diagnostics":[{"path":"docs/notes/broken.md","line":4,"severity":"error","level_source":"default","code":"LC001","name":"invalid-utf8","message":"file is not valid UTF-8","labels":[{"path":"docs/notes/broken.md","line":4,"text":"0xE9 at byte offset 31 starts a character the next byte does not continue"}],"children":[{"kind":"help","text":"save the file as UTF-8","path":null,"line":null}]}],"summary":{"subjects":3,"errors":1,"warnings":0},"coverage":[{"path":"docs/notes/todo.md","ungoverned":["outline","budget"],"cause":null,"skipped_by":[]},{"path":"docs/code/guide.md","ungoverned":[],"cause":"refused-path","skipped_by":["docs/code/guide.md"]},{"path":"docs/code/linked.md","ungoverned":[],"cause":null,"skipped_by":[],"unchecked":true}]}
```


### Exit Status

| Code | Meaning |
|------|---------|
| `0`  | No diagnostic is an error; warnings and ungoverned parts do not count |
| `1`  | An error diagnostic, including a failed spec or unreadable `docs/` path (`LC002`) |
| `2`  | No root; unlistable `docs/` or `docs/__meta__/`; scan-blocking refusal outside reported item reads; changed snapshot entry; invalid level value or usage. A refused non-item file inside a skill scan reports `error: cannot snapshot file <path>: permission denied` without a `caused by:` line or absolute path. Errors print to stderr; usage errors follow [cli](cli.md) |

## Limitations

- Comma-separated level values are not supported. Alias codes remain accepted; no alias-code warning is emitted.
- Warnings do not fail the run: [`LC207`](../rulebook/LC207-unknown-field.md),
  [`LC505`](../rulebook/LC505-extension-link.md), [`LC506`](../rulebook/LC506-missing-base-link.md),
  [`LC507`](../rulebook/LC507-mutual-link.md) or [`LC101`](../rulebook/LC101-reserved-corpus-overlap.md),
  all exit 0. LC507 puts help before note.
  `LC101` is warning by default; findings at error level make the run exit 1.
- A subject shows `--> path` without an excerpt. Unreadable source appears as `= at path:line: text`;
  excerpts cover documents, skills, resources and specs. A BOM is omitted from excerpted line 1.
- Skills without `docs/__meta__/` need `--root`.
- Checks cover machine decisions; review judges meaning.

## Findings

| Rule | Reported when |
|------|---------------|
| `LC0xx` | Engine conditions are errors with no rule level. `LC001` invalid-utf8 reports a file that cannot be decoded, including a structure file; `LC002` unreadable-path reports a workspace path the run cannot read, list or follow; `LC003` malformed-structure-file reports a structure file that breaks the format or states no rule; `LC004` unusable-structure-file reports a well-formed structure file with rules that repeat, contradict each other or cannot be applied. |
| `LC1xx` | Workspace checks: `LC101` reserved-corpus-overlap, a directory under `docs/` has a reserved corpus name such as `skills`; warning by default. `LC102` escaping-symlink, a symlink an agent reaches whose chain leaves the repository. |
| `LC2xx` | Frontmatter checks use applicable schemas, including the builtin Agent Skills specification by default. `LC204` compares skill names with listed directories. `LC201` missing-frontmatter, `LC202` invalid-yaml, `LC203` non-mapping-frontmatter, `LC204` name-mismatch, `LC205` duplicate-key, `LC206` missing-field, `LC207` unknown-field (a warning), `LC208` wrong-type, `LC209` invalid-value, `LC210` invalid-frontmatter, `LC211` malformed-allowed-tools (a warning; pattern whitespace stays intact), `LC212` allowed-tools-too-long (a warning over 500 characters), `LC213` too-many-fields (`maxProperties`, an error), `LC214` too-few-fields (`minProperties`, an error) |
| `LC3xx` | Outline checks: a document's H1 title and sections against its structure files. `LC301` missing-title, `LC302` extra-title, `LC303` title-not-first, `LC304` empty-section, `LC305` forbidden-section, `LC306` missing-section, `LC307` section-out-of-order, `LC308` unexpected-section, `LC309` invalid-title |
| `LC4xx` | Length limits: a document's tokens or declared lines budget, a section's or its title's words or characters, and the builtin Agent Skills layer's 500-line skill cap. `LC401` too-many-tokens, `LC402` too-many-lines, `LC403` section-too-many-words, `LC404` title-too-many-words, `LC405` title-too-long |
| `LC5xx` | Links in structured documents and skills. `LC501` absolute, `LC502` broken fragment, `LC503` broken, `LC504` escaping, `LC505` extension-link (link to same-directory name extension; warning; also checks specs), `LC506` missing-base-link (an extension omits its nearest existing document or spec ancestor under `References`; warning; also checks specs), `LC507` mutual-link (documents in different corpora link each other; warning) |

`LC505`–`LC507` check reference direction in [spec](spec.md#references-point-to-the-base).

Each reported structure-file failure appears once at that file.
 `LC001` points to the first invalid byte; `LC002`–`LC004` are whole-file diagnostics with help before notes.
`LC002` covers unreadable paths, unknown files and unlistable nested directories. Unreadable specs and documents count as subjects; unknown paths do not. Resource and `SKILL.md` aliases appear in coverage at their paths, naming the refused target; non-item targets keep `LC002`, and the aliasing item is skipped. Sibling resources and unaffected subjects continue. A directory alias appears at its path, never at the skill's `SKILL.md`.

`LC208` ends with a schema example; `LC209` labels malformed skill names with their pattern. `LC210` reports whole-block constraints without a label; its note gives the validator's wording. `LC212`–`LC214` and `LC4xx` label the amount over the limit.

## References

- [cli](cli.md) - Base: the command line and the options every command shares
- [workspace](workspace.md) - Dependency: the documents, skills and snapshot the command reads
- [spec](spec.md#references-point-to-the-base) - Dependency: the spec files the rules read and their reference direction
- [frontmatter](frontmatter.md) - Related: the values the block accepts and the `LC202` and `LC205` findings
- [cli-inspect](cli-inspect.md) - Related: shows the subjects this command checks
- [cli-rule](cli-rule.md) - Related: prints the page of a rule by the code a diagnostic prints

## Code References

- `src/lorecraft/cli/app.py` - Global `--no-agent-skills-spec`
- `src/lorecraft/cli/commands/check.py` - Command and level options
- `src/lorecraft/cli/check_run.py` - Rule run and exit status
- `src/lorecraft/cli/root.py` - Root discovery
- `src/lorecraft/cli/subjects.py` - Subject selection
- `src/lorecraft/cli/diagnostics.py` - Short/JSON output, coverage and summaries
- `src/lorecraft/cli/diagnostic_text.py` - Full text renderer
- `src/lorecraft/cli/sources.py` - Source lines
- `src/lorecraft/cli/terminal.py` - Text style
- `src/lorecraft/cli/output.py` - Output and color choices
- `src/lorecraft/engine/skip.py` - Rules over subjects
- `src/lorecraft/rules/table.py` - Enabled rules and severity
- `src/lorecraft/cli/level_arguments.py` - Level arguments
- `src/lorecraft/rules/level_resolution.py` - Rule level resolution
- `src/lorecraft/rules/` - The rules, one module each, in a package per group
