---
name: "prd-032-language-server"
description: "Language server delivering editor and agent diagnostics over governed documents and skills with incremental revision advancing and freshness guarantees"
type: "prd"
status: "draft"
---

# Language Server

## Problem

Writers and autonomous coding agents editing documentation and agent skills in Lorecraft-governed
repositories currently receive feedback only after saving files and executing batch CLI commands such as
`lorecraft check`. This batch cycle introduces friction, delays detection of structural and formatting
mistakes, and forces agents into slow trial-and-error check-edit loops.

An interactive Language Server Protocol (LSP) service is needed to deliver immediate diagnostics
directly into editor buffers and agent environments as changes are typed. Because governed repositories
can contain hundreds of documents and complex rule hierarchies, this service cannot afford to
re-evaluate the entire repository on every keystroke. It requires an incremental execution model that
advances revisions, carries forward valid memoized results, and provides freshness barriers so agents
never act on stale or superseded findings, while remaining strictly consistent with batch checks.

## Goals

- Provide a language server interface serving editors and coding agents working in a repository that
  uses Lorecraft.
- Deliver diagnostics as open files change, mapped accurately to document positions and line ranges.
- Scope analysis strictly to governed documents, specs, skills, and skill resources, matching the lint
  engine's governance bounds.
- Maintain strict equivalence of reported diagnostics between the server and the batch lint engine on
  any identical workspace revision.
- Advance revisions incrementally by carrying over valid memoized query results across keystrokes and file
  events, stopping evaluation early when intermediate outputs are unchanged.
- Ensure freshness safety so clients distinguish completed current results from in-flight, cancelled, or
  superseded computations.

## Non-Goals

- General source code linting: the server analyzes only the documents, specifications, and skills
  governed by Lorecraft.
- Code actions, quick fixes, and automated workspace edits: automated repair actions are out of scope for
  this initial release and deferred to a follow-up release.
- Persisting cached results to disk across separate server processes in this initial release: query
  results remain persistable data, but cross-process persistence and warm starts are deferred.
- Semantic features outside diagnostics (such as autocompletion, hover documentation, document formatting,
  or go-to-definition): these are deferred to future milestones.
- Dedicated custom daemon wrappers, resident socket forwarders, or external tool bridges: clients
  communicate over standard LSP transports.

## User Stories

### US-1: Receive diagnostics while editing (P1)

As a writer editing a governed document in an editor, I want diagnostics to appear and update as I type,
so that I identify syntax, structure, and rule violations immediately without running a terminal check.

**Independent test:** Start the language server, open a governed document with a missing required
section, and verify that a diagnostic is published for that file over the protocol.

```gherkin
Scenario: Reporting a missing required section
  Given a running language server connected to a workspace
  When the editor opens a governed document that omits a required section
  Then the server publishes a diagnostic pointing to the expected location of the missing section
```

```gherkin
Scenario: Clearing diagnostics when an error is resolved
  Given an open document reporting a structural diagnostic
  When the writer adds the missing section into the buffer
  Then the server publishes an updated diagnostic list for that document with the diagnostic removed
```

### US-2: Verified diagnostic loop for autonomous agents (P1)

As an autonomous coding agent communicating with the language server, I want to synchronize buffer edits
and obtain verified current diagnostics for an affected scope, so that I can validate repairs without
running a full batch check or acting on stale results.

**Independent test:** Drive the server over standard input and output with a headless client, send a
sequence of rapid document updates, and verify that reported diagnostics match the latest buffer revision
rather than intermediate superseded edits.

```gherkin
Scenario: Agent receives current diagnostics for latest edit
  Given a headless agent session connected to the language server
  When the agent synchronizes an edited document buffer
  Then the server returns diagnostics matching that exact buffer version
```

```gherkin
Scenario: Obsolete analysis discarded during rapid edits
  Given an in-flight diagnostic evaluation on an earlier buffer revision
  When the agent synchronizes a newer buffer revision before the earlier evaluation finishes
  Then the server discards the obsolete evaluation and reports diagnostics for the newer revision
```

```gherkin
Scenario: Complete headless agent repair lifecycle
  Given a headless agent session started without a graphical editor
  When the agent opens an invalid document, applies a repair edit, and modifies a governing specification
  Then the server reports initial findings, clears them upon repair, and publishes updated findings for the specification change
```

### US-3: React to background workspace file changes (P1)

As a writer switching branches or running background generators, I want the server to update diagnostics
when governed files or specifications change on disk, so that my view reflects the current workspace state.

**Independent test:** Modify a specification file on disk outside the editor, and verify that the server
re-evaluates open documents governed by that specification.

```gherkin
Scenario: Specification change invalidates governed document diagnostics
  Given an open document that conforms to its current governing specification
  When an external tool modifies the specification on disk to require an additional section
  Then the server publishes new diagnostics for the open document reflecting the updated specification
```

## Requirements

- **FR-001:** WHEN an editor opens, edits, or closes a file, THE SYSTEM SHALL track the current buffer
  content as the latest revision of that file, taking precedence over disk content.
- **FR-002:** WHEN an open file's buffer content changes, THE SYSTEM SHALL publish diagnostics for that file
  over the language server protocol.
- **FR-003:** WHEN a watched workspace file changes on disk, THE SYSTEM SHALL incorporate the change into
  the next workspace revision.
- **FR-004:** IF a changed workspace file is a specification or configuration, THEN THE SYSTEM SHALL
  invalidate every document and skill governed by that specification or configuration.
- **FR-005:** THE SYSTEM SHALL translate every rule occurrence and engine diagnostic in a governed file into
  a language server diagnostic carrying severity, rule code, message, primary line range, related locations,
  and documentation link.
- **FR-006:** THE SYSTEM SHALL publish diagnostics only for files that are governed documents, specifications,
  skills, or skill resources.
- **FR-007:** WHEN a file is cleared of all rule violations, THE SYSTEM SHALL publish an empty diagnostic
  list for that file.
- **FR-008:** WHEN advancing from one revision to the next, THE SYSTEM SHALL reuse every memoized query result
  whose inputs and dependencies are unchanged by the revision diff.
- **FR-009:** WHEN a recomputed intermediate query yields a value equal to its previous revision value, THE
  SYSTEM SHALL stop downstream recomputation through early cutoff.
- **FR-010:** IF a file in the workspace cannot be parsed or decoded, THEN THE SYSTEM SHALL publish an engine
  diagnostic for that file and continue serving other files.
- **FR-011:** WHILE an earlier revision evaluation is in flight, IF a newer revision arrives, THEN THE
  SYSTEM SHALL suppress publishing diagnostic results from the superseded revision.
- **FR-012:** THE SYSTEM SHALL operate as a headless server communicating over standard input and output
  without requiring a graphical editor host.
- **NFR-001:** FOR ANY workspace revision, THE SYSTEM SHALL publish diagnostics that are identical in rule
  code, severity, and message to the diagnostics reported by batch checks on the same workspace state.
- **NFR-002:** THE SYSTEM SHALL update diagnostics for an edit on an open document with latency suitable for
  interactive editor and agent feedback.
- **NFR-003:** THE SYSTEM SHALL keep all query results as persistable data values across revisions.

## Edge Cases

- What happens when a file is edited in the buffer but unsaved on disk? The buffer's in-memory content takes
  precedence over disk contents for that revision.
- What happens when an ungoverned file is opened in the editor? The server publishes an empty diagnostic list
  for that file and ignores it for rule evaluation.
- What happens when a rapid succession of edits arrives before a revision computation finishes? The server
  advances to the latest revision and cancels or discards obsolete in-flight computations.
- What happens when a file is deleted from disk while open in the editor? The server retains the buffer
  revision until closed, or reports the deletion once closed.
- What happens when a specification on disk contains a syntax error? The server reports an engine
  diagnostic for the specification and preserves the last valid governance model or reports affected
  documents as unvalidated according to resilient loading rules.

## Key Entities

- **Language Server:** A process implementing the Language Server Protocol that communicates with editors
  and agents over standard input and output.
- **Buffer Revision:** The in-memory text and version of a document maintained by the editor across change
  notifications.
- **Revision Diff:** The set of changed, added, or removed inputs between the previous database revision and
  the next.
- **Carry-Over:** The reuse of memoized query entries from an earlier revision whose dependencies did not
  change.
- **Early Cutoff:** The termination of downstream query re-evaluations when a recomputed result equals its
  predecessor.
- **Freshness Barrier:** A synchronization mechanism ensuring that diagnostics received by a client belong
  strictly to the latest requested revision.

## Success Criteria

- **SC-001:** Opening an invalid governed document in a language server client displays diagnostics that
  match the codes and line positions reported by `lorecraft check`.
- **SC-002:** Editing an open document to fix a violation clears the diagnostic without restarting the server.
- **SC-003:** An autonomous agent synchronizing rapid buffer edits receives diagnostics matching the latest
  buffer revision without receiving stale findings from earlier superseded edits.
- **SC-004:** Modifying a specification on disk immediately updates diagnostics for open documents governed
  by that specification.
- **SC-005:** Editing one document in a large workspace recomputes only queries affected by that document's
  change, leaving unaffected query entries untouched.
- **SC-006:** A headless client executes a complete session over standard input and output without an
  editor host.

## Assumptions

- Editors and agent harnesses connect to the language server via standard input/output using JSON-RPC.
- The repository structure follows Lorecraft corpus specifications where specs reside in `docs/__meta__/`
  and skills in `.agents/skills/`.

## References

- [prd-008-structured-checks](prd-008-structured-checks.md) - Related: The lint engine rules and diagnostics delivered over the protocol
- [adr-005-incremental](adr-005-incremental.md) - Related: The incremental computation model, revision advancing, and carry-over rules
