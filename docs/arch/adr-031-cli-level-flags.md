---
name: "adr-031-cli-level-flags"
description: "Command-line level flags on lorecraft check: -A, -W and -D flags override default and config levels, with specificity precedence and -D warnings elevation. Load when parsing check flags, resolving rule levels or formatting diagnostics"
type: "adr"
status: "accepted"
---

# Command-Line Level Flags on `lorecraft check`

> [!NOTE]
> Supersedes in part [adr-011](adr-011-rules-engine.md): the passage in "Levels, Configuration and Selection" stating "There is no level option on the command line: levels live in the configuration alone, so a local run and CI agree on one revision (NFR-001)" and the selection mechanism (`--select` and `--ignore`). That record stays binding outside these passages.

This record specifies command-line level flags on `lorecraft check`, superseding the command-line restriction in [adr-011](adr-011-rules-engine.md) and settling the open question of [prd-008](prd-008-structured-checks.md) `FR-026`.

## Context

Today, `lorecraft check` cannot alter a rule's severity level. Each rule has a default level (`allow`, `warn` or `deny`), and configuration file support is deferred. Without command-line level flags:
- A user or CI pipeline cannot make a rule advisory or promote a warning to a hard failure.
- CI cannot gate on warnings (`-D warnings`) while local development remains lenient.
- A rule whose default level is `allow` cannot be enabled on the command line.

Additionally, [adr-011](adr-011-rules-engine.md) specified filtering runs via `--select` and `--ignore`. Retaining a parallel filtering mechanism beside level flags creates conflicting semantics and unnecessary surface. Instead, `--select` and `--ignore` are removed: every run checks every enabled rule, and a run is narrowed directly using level flags (`-A ALL -D <code>`).

## Decision

1. **Source hierarchy.** Level resolution follows strict source order, from lowest to highest precedence:
   - Rule default level (`allow`, `warn`, or `deny`)
   - Configuration file (deferred)
   - Command-line level flags (`-A`/`--allow`, `-W`/`--warn`, `-D`/`--deny`)
   - Inline directives (deferred suppress-only directives, which beat `-D`)

2. **Flags and selectors.** `lorecraft check` takes repeatable level flags, each taking exactly one value:
   - `-A`, `--allow`
   - `-W`, `--warn`
   - `-D`, `--deny`

   Accepted selectors are:
   - Full rule code (e.g. `LC201`)
   - Alias code (e.g. `MD040`, resolving silently to its canonical rule code)
   - `ALL` (applies to all rules)
   - `warnings` (reserved selector valid only for `-D`/`--deny`)

   Prefix selectors, group selectors, rule names, and comma-separated values are rejected with exit code 2 before any subject is checked. `-A warnings` and `-W warnings` are usage errors. Setting `-W` or `-D` on a rule whose default is `allow` enables the rule, superseding ADR-011's restriction that only configuration files could enable rules.

3. **Command-line precedence.** Precedence among flags on the command line is resolved by specificity, not argument order:
   - A specific rule code overrides `ALL` regardless of flag ordering (e.g. `-D ALL -A LC201` and `-A LC201 -D ALL` both result in `LC201` at `allow` and all other rules at `deny`).
   - Assigning conflicting levels to the same rule code (or a code and its alias) on the command line (e.g. `-A LC201 -D LC201`) is a usage error that exits 2 before any subject is checked, mirroring the configuration principle that one rule never has two settings.

4. **Elevation via `-D warnings`.** `-D warnings` is evaluated after all rule-level overrides are resolved. It raises every resolved diagnostic at `warn` to `error`, causing the run to fail on warnings while preserving the rule's underlying configured level. Settles [prd-008](prd-008-structured-checks.md) `FR-026`.

5. **Validation.** Unknown, malformed, or invalid selectors (including prefixes, groups, comma-separated values, or `-A warnings`) are usage errors that exit 2 before any subject is checked (satisfying `FR-025`). Selectors are parsed and validated at the CLI boundary into `AllRules | RuleCode | Warnings` alongside the associated `Level`.

6. **Provenance in reports.** When a diagnostic's effective level differs from its default level:
   - Human-readable text output includes an explanatory note naming the flag as the user wrote it (e.g. ``note: `-D MD040` requested on the command line``, or ``note: `-D warnings` elevated warning to error``), while the diagnostic itself carries the canonical Lorecraft code.
   - Machine-readable JSON output includes a `level_source` field (`default | config | cli`).

7. **Invariants kept.** Levels are applied after detection. No rule query or judgement reads CLI flags or levels; rule results remain pure and cacheable across runs.

## Non-Goals

- `-F`/`--forbid`: Deferred until configuration files introduce layered override scopes where immutable freeze semantics are meaningful.
- `--force-warn` and `--cap-lints`: Out of scope.
- Prefix and group selectors: Not supported.
- Inline directives: Remain suppress-only when introduced; not expanded to level elevation.
- `--select` and `--ignore`: Removed from `lorecraft check`.

## Consequences

- Users and CI environments can enforce strict checks (`-D warnings` or `-D ALL`) or selectively enable experimental rules (`-W CODE`) without touching repository configuration.
- Repeatable flag combinations are deterministic and order-independent due to specificity-based resolution and the rejection of conflicting levels.
- The command-line surface is simplified: filtering is achieved through level assignments (`-A ALL -D <CODE>`), removing the redundant `--select` and `--ignore` flags and their interplay.
- Diagnostic output clearly identifies why a rule was reported at a non-default level, preserving the user's chosen selector identity in provenance notes.

## Alternatives Considered

- **Argument order precedence (last flag wins).** Used by rustc/Clippy. Rejected because Lorecraft treats conflicting levels on the same rule as an explicit usage error to prevent subtle script ordering bugs and mirror configuration file validation.
- **Prefix and group selectors.** Considered to allow blanket configuration like `-D LC2xx`. Rejected in alignment with LORE-500 rule renumbering: selectors only operate on discrete rule codes and `ALL`.
- **Retaining `--select` and `--ignore` beside level flags.** Rejected because maintaining two parallel ways to include or exclude checks creates ambiguous precedence and confusing warning semantics (such as `-D CODE --ignore CODE`). Narrowing runs via `-A ALL -D <CODE>` is expressive, consistent with compiler workflows, and unifies rule execution with level resolution.
- **Comma-separated values.** Rejected because comma-separated lists add syntax edge cases and failure modes without providing any capability not already served by repeating the flag.
- **Deprecation warnings for alias codes.** Rejected because alias codes are permanent compatibility mappings for rules absorbed from upstream linters, not deprecated syntax; stderr is reserved for actual errors and failures.

## Checklist

- [ ] `lorecraft check` accepts repeatable `-A`/`--allow`, `-W`/`--warn`, and `-D`/`--deny` flags taking one rule code, alias, or `ALL` each
- [ ] `-D warnings` is accepted and elevates warnings to errors after detection
- [ ] Passing `warnings` to `-A` or `-W` exits 2 before subjects are checked
- [ ] Conflicting levels for the same code on the command line exit 2 before subjects are checked
- [ ] Selectors are validated at the CLI boundary; unknown codes, prefixes, groups, or comma-separated values exit 2
- [ ] Alias codes resolve silently to their canonical rule code without stderr warnings
- [ ] A rule code override takes precedence over `ALL` regardless of CLI flag order
- [ ] Setting `-W` or `-D` on a default-`allow` rule enables the rule
- [ ] Diagnostics with non-default levels carry provenance notes in text naming the written flag, and a `level_source` in JSON reports
- [ ] Rule queries and judgements do not access CLI flags or level state

## References

- [prd-008](prd-008-structured-checks.md) - Requirements: Settles FR-024, FR-025, FR-026, and NFR-001
- [adr-011](adr-011-rules-engine.md) - Supersedes in part: CLI level flag restrictions and selection passages
- [adr-009](adr-009-rules.md) - Foundation: Rule declarations, codes, and index
- [adr-010](adr-010-diagnostics.md) - Foundation: Diagnostic reporting and notes
