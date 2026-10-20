---
name: "prd-014-resilient-model-loading"
description: "A workspace that partly fails to load is still checked: each spec, corpus or skill that cannot be read or used is reported where it fails, and everything it does not touch is checked as if nothing had failed"
type: "prd"
status: "approved"
---

# Resilient Model Loading

## Problem

Before Lorecraft checks a single document, it reads what the repository declares: the specs, the corpora, the
skills directories and the skills in them. Today any one thing in that declaration that cannot be read or used stops
the run. That includes a structure file a writer is still editing, a corpus directory the process cannot list, or a
skill whose link points nowhere. The user gets one error and an exit status of 2, and nothing about the rest of the
workspace. One broken namespace spec hides every diagnostic of every other corpus. A CI job learns only that the
check could not run, and has to be fixed before it says anything else.

Lorecraft is heading towards an LSP-style mode that checks a workspace while it is being edited. In that mode a
spec is often half-written for minutes at a time, and stopping on it would mean no feedback exactly when the writer
needs it. The same workspace has to serve two consumers:

- a CI check, where a clean result must mean the document was checked against every spec that governs it;
- an LSP-style fast feedback loop, which has to keep working on a workspace that is partly broken.

## Goals

- A failure to load part of the workspace is reported as a diagnostic at the place it happened, under a code of its
  own.
- Everything a load failure does not touch is checked exactly as it would be with no failure.
- In a check run, a document that a failed spec would govern is skipped and listed in coverage with the reason,
  never reported as clean.
- In the LSP-style mode, such a document is checked against the specs that did load, and its result is labelled
  partial.
- What stops a run outright stays limited to what makes checking impossible: finding the root, reading a path
  outside the declaration, listing the documentation root or the spec directory, and the command line's own
  input.

## Non-Goals

- **Building the LSP-style mode.** Its requirements are stated here (US-4) so that loading serves both consumers from
  one model. The mode itself is deferred until the long-lived runtime exists, as
  [prd-008](prd-008-structured-checks.md) defers it.
- **Keeping the last good spec in a check run.** A check run reads one revision and has no earlier one to fall
  back on. Carrying an earlier revision's spec forward belongs to the LSP-style mode (FR-013).
- **Using part of a broken structure file.** A structure file that fails is failed whole. Rules read from a file that
  does not decode could mean something other than what its writer wrote.
- **Changing failures outside the declaration.** Root discovery, a path outside the declaration that cannot be read,
  and an invalid selection still stop the run with an error, as today.
- **Amending prd-008.** Codes, coverage and the output shape are prd-008's, and this PRD builds on them without
  changing them.

## User Stories

### US-1: A broken spec does not hide the rest (P1)

As a maintainer running the check in CI, I want a spec that cannot be read or used reported as a diagnostic,
with every document it does not govern still checked, so that one broken file does not hide the state of the rest of
the repository.

**Independent test:** Check a workspace with two corpora, where one corpus's structure file is invalid and the other
corpus holds a document that breaks a rule.

```gherkin
Scenario: An invalid structure file
  Given a workspace where the structure file of one corpus states rules that contradict each other
  And a document in another corpus that breaks a rule
  When the maintainer checks the workspace
  Then an error diagnostic is reported on the invalid structure file, under its code
  And the other document's diagnostic is reported as it would be with no broken file
  And the run fails with the status for findings
```

```gherkin
Scenario: A structure file that cannot be read
  Given a workspace where one structure file cannot be read
  When the maintainer checks the workspace
  Then an error diagnostic is reported on that structure file
  And every corpus the file does not govern is checked
```

### US-2: Know what was not checked, and why (P1)

As a maintainer, I want every document skipped because of a load failure listed in coverage with the spec that
failed, so that a passing check never means a document was checked when it was not.

**Independent test:** Check a workspace where a namespace spec that governs some documents of a corpus fails
to load.

```gherkin
Scenario: A failed namespace spec
  Given a corpus whose namespace spec for one namespace fails to load
  When the maintainer checks the workspace
  Then each document in that namespace is listed in coverage as skipped, naming the failed spec
  And no diagnostic of any rule is reported for those documents
  And the corpus's other documents are checked against the corpus spec
```

```gherkin
Scenario: Coverage in machine-readable output
  Given a workspace where a spec fails to load
  When the maintainer checks it with machine-readable output
  Then the coverage lists each skipped document with the reason and the failed spec
```

### US-3: An unreadable corpus or skill is reported where it is (P2)

As a writer, I want a corpus directory or a skill that cannot be read reported at its path, with the rest of the
workspace checked, so that I can fix the one thing that is wrong.

**Independent test:** Check a workspace with one corpus directory that cannot be listed and one skill whose link
cannot be resolved.

```gherkin
Scenario: A corpus that cannot be listed
  Given a workspace where one corpus directory cannot be listed
  When the writer checks the workspace
  Then an error diagnostic is reported at that directory
  And every other corpus is checked
```

```gherkin
Scenario: A skill that cannot be resolved
  Given a skills directory where one skill is a link that cannot be resolved
  When the writer checks the workspace
  Then an error diagnostic is reported at that entry
  And every other skill and every document is checked
```

### US-4: Feedback while a spec is being edited (P3)

As a writer using the LSP-style mode, I want documents still checked while a spec they answer to is broken,
with each result marked partial, so that I keep getting feedback while I fix the spec.

**Independent test:** In the LSP-style mode, break a namespace spec and edit a document it governs.

This story is a requirement on the deferred LSP-style mode. Nothing in this release builds it.

```gherkin
Scenario: Checked against the specs that loaded
  Given a document governed by its corpus spec and by a namespace spec that fails to load
  When the writer edits the document in the LSP-style mode
  Then the document's diagnostics against the corpus spec are shown
  And the result is labelled partial, naming the spec that failed
```

## Requirements

- **FR-001:** IF a structure file cannot be read, THEN THE SYSTEM SHALL report one error diagnostic on that file
  and go on checking.
- **FR-002:** IF a structure file is not in its dialect's shape, or states rules that cannot be applied, THEN THE
  SYSTEM SHALL report one error diagnostic on that file, naming what is wrong, and go on checking.
- **FR-003:** IF a corpus directory cannot be listed, THEN THE SYSTEM SHALL report one error diagnostic at that
  directory and check every other corpus.
- **FR-004:** IF a skills directory, a skill or a skill's main file cannot be listed or resolved, THEN THE
  SYSTEM SHALL report one error diagnostic at its path and check every other skill and every document.
- **FR-005:** IF the documentation root or the spec directory cannot be listed, THEN THE SYSTEM SHALL stop
  the run with an error naming the directory, as it does when the root cannot be found, since nothing can be
  checked.
- **FR-006:** THE SYSTEM SHALL report each load failure once, at its origin, never once per subject it affects.
- **FR-007:** THE SYSTEM SHALL report a load failure under a code of the engine's group, one code for each kind of
  fix, and name in the diagnostic the case that occurred ([prd-008](prd-008-structured-checks.md) FR-009, FR-012).
- **FR-008:** THE SYSTEM SHALL report a load failure's diagnostic whatever the configuration and the selection, as
  it reports a file that cannot be decoded ([prd-008](prd-008-structured-checks.md) FR-020).
- **FR-009:** THE SYSTEM SHALL check every subject that no load failure touches as it would with no load failure.
- **FR-010:** WHILE a check run judges a document that a spec which failed to load would govern, THE SYSTEM
  SHALL run no rule over the document and list it in coverage as skipped.
- **FR-011:** THE SYSTEM SHALL report each skipped document with the reason and each spec whose failure caused
  it, in the text and in the machine-readable output ([prd-008](prd-008-structured-checks.md) FR-019, FR-021).
- **FR-012:** WHERE the LSP-style mode judges a document that a spec which failed to load would govern, THE
  SYSTEM SHALL check the document against every governing spec that loaded, and label the result partial,
  naming each spec that failed.
- **FR-013:** WHERE the LSP-style mode checks a document against a spec carried over from an earlier revision
  in which it loaded, THE SYSTEM SHALL label the result as checked against that earlier version.
- **FR-014:** WHEN a check run reports a load failure, THE SYSTEM SHALL exit with the status for findings.
- **FR-015:** IF the root cannot be found, a path outside the declaration cannot be read, or the command line's
  input is invalid, THEN THE SYSTEM SHALL stop the run with an error, as before.
- **FR-016:** THE SYSTEM SHALL publish a reference page for each load-failure code, saying what fails and how to fix
  it ([prd-008](prd-008-structured-checks.md) FR-028).
- **NFR-001:** THE SYSTEM SHALL produce identical output for the same workspace revision with the same load
  failures ([prd-008](prd-008-structured-checks.md) NFR-001).
- **NFR-002:** THE SYSTEM SHALL carry, for every load-failure code, a case that triggers it and a near miss that
  does not ([prd-008](prd-008-structured-checks.md) NFR-006).

## Edge Cases

- **A corpus spec fails while its namespace specs load.** Every document of the corpus is skipped
  (FR-010), since the corpus spec governs each one.
- **A document's corpus cannot be listed.** The document is not known to the run, so it is neither checked nor listed
  as skipped. The diagnostic at the directory stands for it (FR-003).
- **A skills directory two agents declare cannot be listed.** It is one failure at one path, reported once (FR-006).
- **A structure file fails in two ways.** It is reported under the first condition its loading meets. A second
  condition shows once the first is fixed.
- **A failed spec governs no document.** Its diagnostic is still reported, and coverage lists no skipped
  document for it.
- **A link on the way to a unit of the declaration cannot be followed.** A symlink whose target the run cannot
  read, or an entry it cannot inspect on a link chain it follows, still stops the run with an error, since no load
  failure stands for it yet. It is the one refusal inside the declaration that SC-005 excepts besides FR-005.
- **The documentation root or the spec directory cannot be listed.** No corpus and no spec is known, so
  nothing can be checked and the run stops with an error (FR-005), whatever else loaded. The skills are not checked
  either: a report that covered them alone would read as a clean result for the whole workspace.

## Key Entities

- **Load failure:** Part of the declaration that could not be read or used: a structure file, a corpus directory, a
  skills directory, a skill or a skill's main file. It has a place, a condition and a code.
- **Skipped subject:** A document that a check run did not judge because a spec governing it failed to load. It
  is coverage, never a diagnostic.
- **Partial result:** A document's diagnostics in the LSP-style mode, judged against only the governing specs
  that loaded, and labelled with the ones that did not.
- **Consumer policy:** What a consumer does with a document whose governing specs include a failed one: skip it
  (a check run) or judge it partially (the LSP-style mode).

## Success Criteria

- **SC-001:** In a workspace with one failed spec, every document it does not govern gets exactly the
  diagnostics it gets with that spec fixed.
- **SC-002:** A check run over a workspace with any load failure never exits successfully.
- **SC-003:** Every document a failed spec would govern is listed as skipped in coverage, and none of them is
  reported with a rule's diagnostic.
- **SC-004:** Every load-failure code has a reference page, a triggering case and a near miss.
- **SC-005:** No failure inside the declaration stops a check run, except a documentation root or spec
  directory that cannot be listed (FR-005), and a link on the way to a unit of the declaration that cannot be
  followed (see Edge Cases).

## Assumptions

- A spec's layers apply by conjunction, so a document governed by a
  failed layer cannot be called clean from the layers that loaded. That is why a check run skips it.
- The LSP-style mode reads the same model as a check run, and differs only in what it does with a document whose
  governing specs include a failed one.

## References

- [prd-008](prd-008-structured-checks.md) - Foundation: The codes, coverage and output shape this PRD builds on
