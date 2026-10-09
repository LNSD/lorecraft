---
name: "adr-007-findings"
description: "What a check reports and how it reaches the user: violations as values, located into findings by the run, stable dotted rule identifiers, the meta spec behind each rule, findings apart from failures, and deterministic text, JSON and exit codes. Load when adding a rule or a check, changing what a check reports, or changing the text output, the JSON output or the exit codes"
type: "adr"
status: "superseded"
---

# Findings

> [!NOTE]
> Superseded by [adr-010-diagnostics](adr-010-diagnostics.md). It binds no code, and records what Lorecraft v0.2
> reports.

## Context

A finding is a rule broken at a line of a document. It travels from a check to the user as a value at every step,
and only the command line turns it into text.

## Decision

### From Violation to Output

A check returns violations: the line, the rule, the message, the meta spec that states the rule, or none
for a rule the check holds itself, and any notes: help or context for fixing it, kept apart from the message. A
violation names no document. The run knows which document it checked, and locates each violation there as a
finding. It collects one report per document or skill, in the order it was
given them, into one run per check. The command line renders the runs as text or JSON and chooses the exit code.
Nothing before it prints.

### A Rule Has a Stable Identifier

Every rule is reported under a dotted identifier: the namespace names who states the rule — the check, or the
corpus whose frontmatter schema states a field — and the rest names the rule. An identifier is part of the
output's contract, so a rule keeps it, and a new rule takes one of its own rather than sharing one.

### A Finding Is Not a Failure

What is wrong with a document is a finding: an unreadable frontmatter block, a missing section, a broken Markdown link. It
is a value the check returns, and the run goes on. What stops Lorecraft from judging at all is a failure: a root
that cannot be found, a meta spec that cannot be decoded, a directory that cannot be listed. It is raised, and
the command line reports it instead of any finding.

### The Output Is Deterministic

The same revision always gives the same output. Reports follow the order of the selection, findings follow the
order a check states them in, and checks run in name order. The exit code is 0 for a clean run, 1 when any check
finds something, and 2 for a failure, after which nothing is printed but the failure.

```python
# ❌ Bad — the check raises on a document it cannot parse: the run stops at the first broken file, every
# document after it goes unchecked, and the user sees a failure instead of a finding with a line
def validate_title(text: str) -> tuple[Violation, ...]:
    block = parse_frontmatter_block(text)
    if block is None:
        raise FrontmatterError('no frontmatter')
    return _title_violations(block)
```

```python
# ✅ Good — the broken block is a fact about the document, reported where it is, and the run goes on
def validate_title(block: FrontmatterBlock | MissingBlock) -> tuple[Violation, ...]:
    if isinstance(block, MissingBlock):
        return (Violation(line=FIRST_LINE, rule='title.frontmatter-missing', message='no frontmatter block'),)
    return _title_violations(block)
```

## Consequences

- Checks stay pure values a test can assert on, and only the command line prints.
- A rule's identifier is part of the output's contract, so changing one is a breaking change.

## Checklist

Before committing code, verify:

- [ ] A violation names the meta spec file that states its rule, or none for a rule the check holds
- [ ] A new rule has a dotted identifier of its own, and no existing identifier changes
- [ ] Help or context for fixing a violation travels as a note, never inside its message
- [ ] A problem in a document is a finding; only what stops judging at all is raised
- [ ] Output order and exit codes stay deterministic for the same revision
- [ ] Nothing below the command line prints or logs

## References

- [adr-010-diagnostics](adr-010-diagnostics.md) - Superseded by: Diagnostics, their order and the exit codes
- [adr-001-snapshot-model](adr-001-snapshot-model.md) - Related: The model and the package roles
- [adr-006-specifications](adr-006-specifications.md) - Related: Where the rules a finding cites come from
- [adr-004-database](adr-004-database.md) - Related: The revision every finding in one report comes from
- [error-boundaries](../code/error-boundaries.md) - Foundation: Where a failure is raised and where it is reported
