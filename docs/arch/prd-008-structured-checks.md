---
name: "prd-008-structured-checks"
description: "One lint engine for the documents and skills Lorecraft governs, replacing separate checks whose rules have no stable identity, no level and no reference"
type: "prd"
status: "draft"
---

# Structured Checks

## Problem

A repository that adopts Lorecraft runs several separate checks, each with its own subcommand, its own report
shape and its own way of naming what it found. A rule is a string spelled where the diagnostic is built: nothing
lists the rules, some identifiers are built from the repository's own corpora, and none has a page a writer can
open to understand a diagnostic and fix it. Every diagnostic fails the run, so a repository cannot turn a rule off or
make it advisory.

New lints are planned on top of these checks, and after them rules over new inputs. Each one added to today's
shape costs another pipeline. The checks have to become one linter first, with rules that are declared,
identified, configured and documented the same way, and cheap to add.

## Goals

- One command checks a file, a directory or the whole workspace, and reports every subject kind in one shape.
- Every rule has a stable code and a name, shown wherever a diagnostic is.
- Every rule has a reference page, readable in the repository and from the command line.
- A repository sets each rule's level: `allow`, `warn` or `deny`.
- Every condition the checks report today is reported by the engine.
- Adding a rule is one self-contained addition, and adding a corpus changes nothing in the engine.

## Non-Goals

- Linting source code: the engine lints the documents and skills Lorecraft governs, nothing else.
- New lints: which rules are added, and their defaults, are designed in their own issues.
- Unchanged output: the engine ships in a breaking release, whose release notes carry the migration.
- Rules loaded from outside Lorecraft: the set of codes is fixed by the release.
- Automatic fixes and inline suppression: a diagnostic leaves room for both, and neither ships here.
- An IDE-like, long-lived mode: re-checking on each change, unsaved content, rejecting a superseded revision's
  results and ranged locations need a runtime a single run cannot exercise, and are deferred until it exists.
- Selection by path in v0.3.0: the command checks the whole workspace (FR-002), and checking a file or a directory,
  FR-003 to FR-007, is deferred to v0.4.0
  ([#442](https://github.com/LNSD/lorecraft/issues/442)).

## User Stories

### US-1: Check anything with one command (P1)

As a writer, I want one command that checks whatever path I give it, so that I do not choose a check per kind
of file.

**Independent test:** Check a file, a directory and the workspace, each holding a known violation.

v0.3.0 delivers the one command over the whole workspace; checking a file or a directory, and both scenarios
below, are deferred to v0.4.0 ([#442](https://github.com/LNSD/lorecraft/issues/442)).

```gherkin
Scenario: A single file
  Given a workspace where two documents each break a rule
  When the writer checks one of them by its path
  Then only that document's diagnostic is reported
```

```gherkin
Scenario: A file that is no subject
  Given a file that no corpus and no skill holds
  When the writer checks it by its path
  Then the run fails with an error naming the file
```

### US-2: Identify a diagnostic by its code (P1)

As a writer, I want every diagnostic to carry its rule's code, so that I can look the rule up, configure it and
refer to it.

**Independent test:** Check a document that breaks one rule, in both output formats.

```gherkin
Scenario: The code is in every output
  Given a document that breaks one rule
  When the writer checks it in the text and the machine-readable output
  Then both show the same code for the diagnostic
```

### US-3: Set a rule's level (P2)

As a maintainer, I want to set each rule to `allow`, `warn` or `deny`, so that a rule my repository does not
want stops failing its runs.

**Independent test:** Check one violating document under each of the three levels.

```gherkin
Scenario: A rule made advisory
  Given a document that breaks a rule the configuration sets to warn
  When the maintainer checks it
  Then the diagnostic is reported as a warning and the run succeeds
```

```gherkin
Scenario: An unknown code
  Given a configuration that names a code no rule has
  When the maintainer checks the workspace
  Then the run fails with an error naming the code
```

### US-4: Look a rule up (P2)

As a writer, I want to read a rule's page from its code or name, so that I can fix a diagnostic without reading
the source.

**Independent test:** Ask for a rule by its code, then by its name.

```gherkin
Scenario: By code and by name
  Given a rule with a code and a name
  When the writer asks for the rule by either
  Then the same page is printed, as the reference holds it
```

### US-5: Add a rule (P3)

As a contributor, I want a new rule to be one self-contained addition, so that adding a check does not mean
editing the engine.

**Independent test:** Add a sample rule over an existing input, and change nothing else.

```gherkin
Scenario: A sample rule
  Given a new rule added with no other edit
  When the contributor checks a document that breaks it
  Then its diagnostic is reported, and its page is in the reference
```

## Requirements

- **FR-001:** THE SYSTEM SHALL report, under a rule, every condition the v0.2 checks report.
- **FR-002:** WHEN a user checks with no path, THE SYSTEM SHALL check the whole workspace.
- **FR-003:** WHEN a user checks a file, THE SYSTEM SHALL check every subject that file is, a skill's resource
  on its own included.
- **FR-004:** WHEN a user checks a directory, THE SYSTEM SHALL check every subject under it.
- **FR-005:** IF a path names a file that is no subject, THEN THE SYSTEM SHALL fail with an error naming it.
- **FR-006:** WHEN the paths a user gives overlap, THE SYSTEM SHALL report each subject once.
- **FR-007:** THE SYSTEM SHALL report a diagnostic about the skill layout only when the paths cover the entry it
  is about.
- **FR-008:** WHERE a user selects or ignores rules for one run, by code or by prefix, THE SYSTEM SHALL report
  only the selected rules' diagnostics.
- **FR-009:** THE SYSTEM SHALL identify every rule by one code, a group prefix and digits, and by one
  kebab-case name.
- **FR-010:** THE SYSTEM SHALL show a diagnostic's code in the text and in the machine-readable output.
- **FR-011:** THE SYSTEM SHALL keep the same set of codes whatever corpora a repository declares, the corpus,
  the field and the governing meta spec travelling as data of the diagnostic.
- **FR-012:** THE SYSTEM SHALL give one code to each condition a rule reports.
- **FR-013:** THE SYSTEM SHALL name each prefix after the mechanism that states its rules, never after a
  subject kind.
- **FR-014:** THE SYSTEM SHALL never give a retired rule's code to another rule.
- **FR-015:** WHEN a configuration names a retired code, THE SYSTEM SHALL report the release that retired it
  and the code that replaces it.
- **FR-016:** THE SYSTEM SHALL report every subject kind in one shape, presented per file.
- **FR-017:** THE SYSTEM SHALL report each diagnostic with its code, severity, location, message, notes and the
  meta spec it comes from.
- **FR-018:** THE SYSTEM SHALL order a report by file path, then by location, then by severity, then by code,
  then by message.
- **FR-019:** THE SYSTEM SHALL report a subject no meta spec governs as coverage, not as a diagnostic.
- **FR-020:** IF a file cannot be decoded, THEN THE SYSTEM SHALL report one diagnostic for it, under a fixed
  code, and fail the run whatever the configuration.
- **FR-021:** WHERE the user asks for machine-readable output, THE SYSTEM SHALL write one document holding the
  diagnostics, a summary and the coverage.
- **FR-022:** THE SYSTEM SHALL report one condition under one code, two rules firing on one line only where
  they are declared to.
- **FR-023:** THE SYSTEM SHALL give every rule a default level: `allow`, `warn` or `deny`.
- **FR-024:** WHERE a configuration sets a level by code or by prefix, THE SYSTEM SHALL apply it, a code's own
  setting winning over its prefix's [NEEDS CLARIFICATION: where does the configuration live?].
- **FR-025:** IF a configuration names an unknown code, prefix or level, THEN THE SYSTEM SHALL fail with an
  error naming it, before checking.
- **FR-026:** THE SYSTEM SHALL count warnings and errors apart, and fail the run only on an error
  [NEEDS CLARIFICATION: is there an option that fails on warnings?].
- **FR-027:** THE SYSTEM SHALL report no diagnostic of a rule whose level is `allow`.
- **FR-028:** THE SYSTEM SHALL publish a reference page per rule, generated from the rule's own declaration:
  its code, name, the release it is stable since, what it checks, and how to fix it.
- **FR-029:** WHEN a user asks for a rule by code or name, THE SYSTEM SHALL print that rule's reference page.
- **NFR-001:** THE SYSTEM SHALL produce identical output for the same workspace revision and configuration.
- **NFR-002:** THE SYSTEM SHALL check this repository, with no path, no slower than v0.2 does.
- **NFR-003:** THE SYSTEM SHALL read only what the selected subjects' enabled rules need.
- **NFR-004:** THE SYSTEM SHALL accept a new rule over an existing input as one addition, with no other edit.
- **NFR-005:** THE SYSTEM SHALL accept a new corpus as the repository's data, with no change to the engine.
- **NFR-006:** THE SYSTEM SHALL carry, for every code, a case that triggers it and a near miss that does not.
- **NFR-007:** THE SYSTEM SHALL build each report from one revision of the workspace.

## Edge Cases

- What happens when a rule set to `allow` is also selected for one run?
- What happens when a directory holds no subject?
- What happens when two rules overlap today, as a name checked against both its filename and its schema?
- What happens when a rule depends on the current date?

## Key Entities

- **Subject:** What a rule judges: a document, a skill, a skill's resource, or an entry of the skill layout.
- **Rule:** One check over a subject, with a code, a name, a group, a default level and a reference page.
- **Code:** A rule's permanent identifier: its group's prefix, then digits.
- **Level:** How a rule is configured: `allow` hides its diagnostics, `warn` reports them as warnings, `deny`
  reports them as errors, which fail the run.
- **Diagnostic:** One rule's occurrence at a location in a subject, reported as an error or a warning.
- **Coverage:** Which subjects were checked, and which no meta spec governs.
- **Revision:** The workspace as it stands at one moment; a change produces the next one.

## Success Criteria

- **SC-001:** Every condition the v0.2 checks report on this repository's test cases is reported under a code.
- **SC-002:** A sample rule is added as one addition, and is reported, configurable and documented with no
  other edit.
- **SC-003:** A writer reaches a diagnostic's reference page from its code in one step.
- **SC-004:** This repository passes the engine under its own configuration, read like any other's.
- **SC-005:** A run over this repository with no path takes no longer than the v0.2 run.
- **SC-006:** No code lacks a triggering case or a near-miss case.

## Assumptions

- A user of today's checks accepts changed output and commands, given a documented migration.
- The rules of later milestones read inputs of the kinds the ported rules already read, or add one new kind
  at a time.
- A meta spec's layers reach a rule by conjunction: each governing meta spec applies on its own, and a rule
  reports each one a subject breaks ([adr-006](adr-006-specifications.md)).

## Open Questions

- **FR-024:** Where does the configuration live?
- **FR-026:** Is there an option that fails on warnings?

## References

- [#315](https://github.com/LNSD/lorecraft/issues/315) - Source: The exploration this PRD consolidates
- [adr-006](adr-006-specifications.md) - Foundation: How a document's meta specs layer onto each other
- [adr-009](adr-009-rules.md) - Leads to: How a rule is declared and identified
- [adr-010](adr-010-diagnostics.md) - Leads to: What a rule reports, and how it reaches the user
- [adr-011](adr-011-rules-engine.md) - Leads to: How a run judges subjects
