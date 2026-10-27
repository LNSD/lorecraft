---
name: "cli-check"
description: "The lorecraft check command: workspace checks, root discovery, rule selection, level flags, text and JSON reports, and exit status. Load when running checks, selecting rules, assigning levels or interpreting reports"
type: "feature"
status: "experimental"
components: "module:lorecraft.cli,module:lorecraft.engine,module:lorecraft.rules"
---

# `lorecraft check`

## Summary

Checks documents and skills against applicable specifications. Refused items are skipped; non-item failures use `LC002`.

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
### Selecting Rules

`--select` is the only filter. It accepts case-sensitive `ALL`, full codes or aliases, comma-separated or repeated;
omitting it checks all rules. Prefix selectors are unknown and exit `2`; selected `allow` rules warn.

Conflicting-level errors name `-A`, `-W`, `-D`; invalid values exit `2` before root discovery. They do not apply levels.

## Configuration

| Argument or option | Default | Env var | Description |
|--------------------|---------|---------|-------------|
| `--no-agent-skills-spec` (`--no-builtin-skills-schema`) | unset | — | Disable the builtin Agent Skills spec and floor, including contradiction preflight; repository specs still apply |
| `--root <path>`    | nearest of working directory and parents holding `docs/__meta__/` | — | The repository root, as [Root Discovery](#root-discovery) describes |
| `--format <text\|short\|json>` | `text` | — | The output format, as [Output](#output) describes |
| `--color <WHEN>` | `auto` | [`NO_COLOR`](https://no-color.org/), [`FORCE_COLOR`](https://force-color.org/) | `text` only. `auto`: nonempty `FORCE_COLOR` enables; else nonempty `NO_COLOR` disables; otherwise stdout's TTY state applies. Empty is unset; any nonempty value, even `0`, is set. Errors red, warnings yellow, messages bold, gutters blue. |
| `--select <selectors>` | `ALL` | — | Run only these rules, as [Selecting Rules](#selecting-rules) describes |
| `-A`, `--allow <code>` | none | — | Allow a code, alias or `ALL`; repeatable |
| `-W`, `--warn <code>` | none | — | Warn on a code, alias or `ALL`; repeatable |
| `-D`, `--deny <code>` | none | — | Deny a code, alias, `ALL` or `warnings`; repeatable |

An unlisted `--format` or `--color` exits `2`. Explicit `always`/`never` wins; the table describes the `auto` precedence.

## Usage

```bash
lorecraft check

lorecraft check --root ../other-repo --format json

lorecraft check --format short

lorecraft check --select LC206,LC403
```

`--no-builtin-skills-schema` is a compatibility alias. `LC204` compares `name` with the skill directory; it never
suggests renaming `SKILL.md`. Without a repository skills spec, opt-out reports `ungoverned for frontmatter, budget`
(exit `0`) even for malformed frontmatter or mismatched names; `LC402`, `LC211` and `LC212` do not run. Default
skill coverage omits `budget`. Excluding required `name`/`description` fails; indirect and cross-layer constraints
are unchecked. See [The Subjects](#the-subjects) and [structure budgets](spec-structure-budget.md).

### Output

In `text`, stdout has blank-line-separated diagnostics with severity, code, message, numbered source and labels. Reported lines underline solid; other labels dotted. Nearby lines group, distant lines use ellipses; `:::` points to another file. Help/notes use `= help:`/`= note:`. For non-default levels, notes name the winning code or group selector. CLI notes use `-W`/`-D` and say `requested on the command line`; configuration notes identify the `warn`/`deny` level and selector. Default levels add no note.

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

On stderr, `text` prints coverage, counts per code group and `checked N subject(s): ...`. Refused items are `skipped, read refused at: <path>`; subjects blocked by refused docs dependencies are `skipped, depends on a refused docs path: <path>`. Refused document/spec reads produce `LC002`; a refused non-item docs path keeps `LC002` even when a skill item aliases it, and that item is also skipped. Other refused skill files remain scan-blocking errors and exit `2`. Symlinked corpora and `.md` entries are not checked; links are not followed or counted.

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

In `json`, stdout is one compact line; stderr holds selection warnings. In text order, `diagnostics` lists `path`, nullable `line`, `severity`, `level_source`, `code`, `name`, `message`, `labels` and `children`. `level_source` is always present: `default` when no override applies, `config` when configuration overrides a rule's level. `summary` counts subjects and severities; load failures are errors, not subjects. `coverage` gives each path's `ungoverned`, `cause` (`refused-path`, `refused-dependency` or null) and refused paths in `skipped_by`; unchecked symlinks add `unchecked: true`:

```json
{"diagnostics":[{"path":"docs/notes/broken.md","line":4,"severity":"error","level_source":"default","code":"LC001","name":"invalid-utf8","message":"file is not valid UTF-8","labels":[{"path":"docs/notes/broken.md","line":4,"text":"0xE9 at byte offset 31 starts a character the next byte does not continue"}],"children":[{"kind":"help","text":"save the file as UTF-8","path":null,"line":null}]}],"summary":{"subjects":3,"errors":1,"warnings":0},"coverage":[{"path":"docs/notes/todo.md","ungoverned":["outline","budget"],"cause":null,"skipped_by":[]},{"path":"docs/code/guide.md","ungoverned":[],"cause":"refused-path","skipped_by":["docs/code/guide.md"]},{"path":"docs/code/linked.md","ungoverned":[],"cause":null,"skipped_by":[],"unchecked":true}]}
```


### Exit Status

| Code | Meaning |
|------|---------|
| `0`  | No diagnostic is an error; warnings and ungoverned parts do not count |
| `1`  | An error diagnostic, including a failed spec or unreadable `docs/` path (`LC002`) |
| `2`  | No root; unlistable `docs/` or `docs/__meta__/`; scan-blocking refusal outside reported item reads; changed snapshot entry; invalid selection or usage. A refused non-item file inside a skill scan reports `error: cannot snapshot file <path>: permission denied` without a `caused by:` line or absolute path. Errors print to stderr; selector usage errors follow [cli](cli.md) |

## Limitations

- Rules use default levels; selection only narrows the run.
- Warnings do not fail the run: [`LC207`](../rulebook/LC207-unknown-field.md),
  [`LC505`](../rulebook/LC505-extension-link.md), [`LC506`](../rulebook/LC506-missing-base-link.md),
  [`LC507`](../rulebook/LC507-mutual-link.md) or [`LC101`](../rulebook/LC101-reserved-corpus-overlap.md),
  all exit 0. LC507 puts help before note.
  `LC101` is selectable; if its level makes it an error, the run exits 1.
- A whole subject shows `--> path` without an excerpt. Unreadable source appears as `= at path:line: text`;
  excerpts cover documents, skills, resources and specs. A BOM is omitted from excerpted line 1.
- Skills without `docs/__meta__/` need `--root`.
- Checks cover machine decisions; review judges what a section says.

## Findings

| Rule | Reported when |
|------|---------------|
| `LC0xx` | Engine conditions are errors with no level; selection and configuration cannot turn them off. `LC001` invalid-utf8 reports a file that cannot be decoded, including a structure file; `LC002` unreadable-path reports a workspace path the run cannot read, list or follow; `LC003` malformed-structure-file reports a structure file that breaks the format or states no rule; `LC004` unusable-structure-file reports a well-formed structure file with rules that repeat, contradict each other or cannot be applied. |
| `LC1xx` | Workspace checks: `LC101` reserved-corpus-overlap, a directory under `docs/` has a reserved corpus name such as `skills`; warning by default. `LC102` escaping-symlink, a symlink an agent reaches whose chain leaves the repository. Select or ignore either by its full code. |
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
