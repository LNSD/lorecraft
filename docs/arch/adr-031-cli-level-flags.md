---
name: "adr-031-cli-level-flags"
description: "Command-line level flags on lorecraft check: -A, -W and -D flags override default and config levels, with specificity precedence and -D warnings elevation. Load when parsing check flags, resolving rule levels or formatting diagnostics"
type: "adr"
status: "proposed"
---

# Command-Line Level Flags on `lorecraft check`

> [!NOTE]
> Proposed to supersede in part [adr-011](adr-011-rules-engine.md): the passage in "Levels, Configuration and Selection" stating "There is no level option on the command line: levels live in the configuration alone, so a local run and CI agree on one revision (NFR-001)" and the mention of group and code prefix selectors for `--select` and `--ignore`. That record stays binding outside these passages, and until this record is accepted.

This record specifies command-line level flags on `lorecraft check`, superseding the command-line restriction in [adr-011](adr-011-rules-engine.md) and settling the open question of [prd-008](prd-008-structured-checks.md) `FR-026`.

## Context

Today, `lorecraft check` can filter which rules run via `--select` and `--ignore`, but cannot alter a rule's severity level. Each rule has a default level (`allow`, `warn` or `deny`), and configuration file support is deferred. Without command-line level flags:
- A user or CI pipeline cannot make a rule advisory or promote a warning to a hard failure.
- CI cannot gate on warnings (`-D warnings`) while local development remains lenient.
- A rule whose default level is `allow` cannot be enabled on the command line, because `--select` only filters and does not change levels.

Additionally, [adr-011](adr-011-rules-engine.md) described `--select` and `--ignore` as accepting group and code prefixes. As settled during rule renumbering, prefixes are not valid selectors; selectors accept only full rule codes, alias codes, and `ALL`. The specification needs to realign with this invariant.

## Decision

1. **Source hierarchy.** Level resolution follows strict source order, from lowest to highest precedence:
   - Rule default level (`allow`, `warn`, or `deny`)
   - Configuration file (deferred)
   - Command-line level flags (`-A`/`--allow`, `-W`/`--warn`, `-D`/`--deny`)
   - Inline directives (deferred suppress-only directives, which beat `-D`)

2. **Flags and selectors.** `lorecraft check` takes repeatable, comma-separated level flags:
   - `-A`, `--allow`
   - `-W`, `--warn`
   - `-D`, `--deny`

   Accepted selectors follow the `--select` grammar:
   - Full rule code (e.g. `LC201`)
   - Alias code (resolves to its canonical code with a stderr warning naming the replacement)
   - `ALL` (applies to all rules)
   - `warnings` (reserved selector valid only for `-D`/`--deny`)

   Prefix and group selectors are rejected. `-A warnings` and `-W warnings` are usage errors.

3. **Command-line precedence.** Precedence among flags on the command line is resolved by specificity, not argument order:
   - A specific rule code overrides `ALL` regardless of flag ordering (e.g. `-D ALL -A LC201` and `-A LC201 -D ALL` both result in `LC201` at `allow` and all other rules at `deny`).
   - Assigning conflicting levels to the same rule code (or a code and its alias) on the command line (e.g. `-A LC201 -D LC201`) is a usage error that exits 2 before any subject is checked, mirroring the configuration principle that one rule never has two settings.

4. **Elevation via `-D warnings`.** `-D warnings` is evaluated after all rule-level overrides are resolved. It raises every resolved diagnostic at `warn` to `error`, causing the run to fail on warnings while preserving the rule's underlying configured level. Settles [prd-008](prd-008-structured-checks.md) `FR-026`.

5. **Interplay with `--select` and `--ignore`.**
   - Levels resolve first; selection then filters the rule table.
   - Setting `-W` or `-D` on a rule whose default is `allow` enables the rule. This supersedes ADR-011's restriction that only configuration files could enable rules.
   - Passing `--select` for a rule left at `allow` produces the existing warning pointing the user to `-W CODE`.
   - Passing contradictory flags, such as `-D CODE --ignore CODE`, suppresses the rule from running and emits an advisory warning on stderr noting the contradiction.

6. **Validation.** Unknown, malformed, or invalid selectors (including prefixes, groups, or `-A warnings`) are usage errors that exit 2 before any subject is checked (satisfying `FR-025`). Selectors are parsed and validated at the CLI boundary into `AllRules | RuleCode | Warnings` alongside the associated `Level`.

7. **Provenance in reports.** When a diagnostic's effective level differs from its default level:
   - Human-readable text output includes an explanatory note (e.g. ``note: `-D LC201` requested on the command line``, or ``note: `-D warnings` elevated warning to error``).
   - Machine-readable JSON output includes a `level_source` field (`default | config | cli`).

8. **Invariants kept.** Levels are applied after detection. No rule query or judgement reads CLI flags or levels; rule results remain pure and cacheable across runs.

## Non-Goals

- `-F`/`--forbid`: Deferred until configuration files introduce layered override scopes where immutable freeze semantics are meaningful.
- `--force-warn` and `--cap-lints`: Out of scope.
- Prefix and group selectors: Not supported.
- Inline directives: Remain suppress-only when introduced; not expanded to level elevation.

## Consequences

- Users and CI environments can enforce strict checks (`-D warnings` or `-D ALL`) or selectively enable experimental rules (`-W CODE`) without touching repository configuration.
- Repeatable flag combinations are deterministic and order-independent due to specificity-based resolution and the rejection of conflicting levels.
- ADR-011's drift regarding prefix selectors for `--select` and `--ignore` is corrected.
- Diagnostic output clearly identifies why a rule was reported at a non-default level.

## Alternatives Considered

- **Argument order precedence (last flag wins).** Used by rustc/Clippy. Rejected because Lorecraft already resolves `--select` and `--ignore` by specificity, and treating conflicting levels on the same rule as an explicit usage error prevents subtle script ordering bugs and mirrors configuration file validation.
- **Prefix and group selectors.** Considered to allow blanket configuration like `-D LC2xx`. Rejected in alignment with LORE-500 rule renumbering: selectors only operate on discrete rule codes and `ALL`.
- **Replacing `--select` entirely with `-A ALL -D <CODE>`.** Rejected because filtering which checks execute and setting severity levels are distinct concerns; retaining `--select` keeps rule filtering decoupled from diagnostic level semantics.

## Checklist

- [ ] `lorecraft check` accepts `-A`/`--allow`, `-W`/`--warn`, and `-D`/`--deny` flags taking rule codes, aliases, and `ALL`
- [ ] `-D warnings` is accepted and elevates warnings to errors after detection
- [ ] Passing `warnings` to `-A` or `-W` exits 2 before subjects are checked
- [ ] Conflicting levels for the same code on the command line exit 2 before subjects are checked
- [ ] Selectors are validated at the CLI boundary; unknown codes, prefixes, or groups exit 2
- [ ] Alias codes resolve to their canonical rule code with a deprecation warning on stderr
- [ ] A rule code override takes precedence over `ALL` regardless of CLI flag order
- [ ] Setting `-W` or `-D` on a default-`allow` rule enables the rule
- [ ] Passing contradictory flags (e.g. `-D CODE --ignore CODE`) omits the rule and logs a warning on stderr
- [ ] Diagnostics with non-default levels carry provenance notes in text and a `level_source` in JSON reports
- [ ] Rule queries and judgements do not access CLI flags or level state

## References

- [prd-008](prd-008-structured-checks.md) - Requirements: Settles FR-024, FR-025, FR-026, and NFR-001
- [adr-011](adr-011-rules-engine.md) - Supersedes in part: CLI level flag restrictions and prefix selector passages
- [adr-009](adr-009-rules.md) - Foundation: Rule declarations, codes, and index
- [adr-010](adr-010-diagnostics.md) - Foundation: Diagnostic reporting and notes
