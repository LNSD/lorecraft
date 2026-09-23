---
name: code-review
description: Deep review of the working branch — rule compliance, bugs, regressions, security, soundness. Use before opening a PR, or when a change needs scrutiny beyond /code-rules-check.
allowed-tools: Bash(git diff *) Bash(git status *) Bash(git merge-base *) Bash(grep *)
---

# Code Review

A thorough review of the current branch, run locally. It performs `/code-rules-check` at review depth — fanned
out across rule groups — and adds what a compliance check cannot see: logic gaps, regressions, security,
safety, and soundness.

The subject is the uncommitted work by default (`git diff HEAD`, `git status`). For a whole branch use
`git diff $(git merge-base HEAD main)...HEAD`. Review only what the diff touches — an unchanged file that
breaks a rule is not this change's finding.

## When to Use This Skill

- Before opening a PR
- After a large, risky, or long-running implementation
- Reviewing someone else's branch locally
- When `/code-rules-check` is clean but the change still warrants scrutiny

For the routine "does this follow the rules?" pass after finishing a piece of work, use `/code-rules-check`
alone — it is a fraction of the cost and is the gate in the development workflow.

## Review Checklist

Please review this code change and provide feedback on:

### 1. Security Concerns

Review for security vulnerabilities:
- Exposed secrets or credentials — a literal token, key or password, and anything that reaches a log line or
  an exception message
- Input validation and sanitization at the boundaries: a document read from disk, its YAML frontmatter, a
  JSON Schema file, a path supplied by the caller
- `yaml.load` on document frontmatter where `yaml.safe_load` is the only safe choice
- A document or schema path joined from caller-supplied parts without containing it inside the corpus
  directory, so `../` escapes the tree being checked
- A subprocess spawned with `shell=True`, or a command line assembled by string interpolation

### 2. Principles Violations

The `principle-*` documents are the design rules, and the `/code-rules` catalog states each one in full — work
from the catalog rather than a list here, which would cover a subset and go stale on the next edit.

Judge the change against all of them. Read a full principle document when you need to *argue* a finding: the
examples and the Pragmatism Caveat are what separate a violation from a deliberate, documented exception, and
a principle finding that ignores the caveat will be rejected.

### 3. Potential Bugs

Look for common programming errors such as:
- Off-by-one errors, especially in line numbers and section boundaries
- Incorrect conditionals
- Use of the wrong variable when several of the same type are in scope
- `min` vs `max`, `first` vs `last`, flipped ordering
- Iterating a `dict` or `set` in an order-sensitive operation — findings reported in a different order on
  every run are a defect, not noise
- A mutable default argument, or a dataclass field sharing one instance across objects

### 4. Unhandled Failure Paths

Identify the paths that raise where nothing locally proves they cannot:
- Indexing or `dict[key]` on data that came from outside — parsed frontmatter, a schema file, a config file
- `int()`, `float()` or a `datetime` parse on an untrusted string
- A bare `except`, or an `except Exception` that swallows the failure and returns a default — a malformed
  document must produce a finding, never a silent pass
- `assert` used to enforce a runtime invariant; `-O` removes it
- A resource left unreleased when the failing path skips the cleanup

**Note**: this overlaps with `docs/code/python-errors-handling.md` and `docs/code/python-exceptions.md`.
Verify compliance with the project's error handling standards.

### 5. Backwards Compatibility

Verify backwards compatibility is maintained:
- A changed public dataclass field — a rename, a removed default, a narrowed type — breaks every caller that
  constructs it by keyword
- A tightened frontmatter schema or structure rule that documents already in a consuming repository cannot
  satisfy, turning a clean corpus into a wall of findings
- A renamed check identifier, or a changed finding shape, that a caller parsing the output depends on
- A renamed or removed public name in a package `__init__.py`

### 6. Code Rules Compliance

Run `/code-rules-check`, forcing its fan-out path regardless of diff size: one agent per rule group, spawned
in a single message, each applying its documents' `## Checklist` items to the diff. That skill owns the
procedure — which documents govern a change, how groups are derived, and the report format. Do not restate
its rules here; they change when `docs/code/` changes.

A finding in this dimension is a rule violation with a document behind it. Anything a reviewer notices that no
document states belongs in the dimensions above and below, not here.

### 7. Testing

Evaluate test coverage and quality:
- Reduced test coverage without justification
- Tests that do not actually test the intended behavior
- Tests with race conditions or non-deterministic behavior
- A test that mocks its own subject, or patches module internals instead of exercising the public surface
- A document-shaped fixture inlined as a string where a checked-in file under `tests/` would let the test
  read the same thing an agent would
- Changes to existing tests that weaken assertions
- Changes to tests that are actually a symptom of breaking changes to user-visible behaviour
- A new marker that is not declared in `pyproject.toml`; `--strict-markers` turns it into a collection error
- A test that needs a network service or credentials: the suite is unit-only, so there is no tier for it and
  `just test-unit` would either reach it or skip it silently — the dependency has to go

### 8. Performance

Check for performance issues:
- The same document read and parsed once per check instead of once per document
- A regex compiled, or a JSON Schema loaded, inside a per-document loop rather than once up front
- A quadratic scan over sections or findings where a single pass, or a lookup by key, would do
- Reading and parsing a whole document when only its frontmatter is needed

### 9. Documentation

Ensure documentation is up-to-date:
- `README.md` and `docs/` reflect current behaviour, and the `justfile` recipes they quote still exist
- `AGENTS.md` marks planned things as planned: a section that calls something "planned, not created" must be
  updated in the same change that creates it
- A new or changed check is reflected in the format specification it enforces, under `docs/__meta__/` — the
  rule a checker applies and the prose stating it change together

### 10. Dead Code

Find dead code that is not caught by ruff:
- A value assigned then overwritten before it is read
- A module, class or function nothing imports, and that no registry discovers by name
- `breakpoint()`, a debugging `print()`, or a commented-out block left behind
- A `TODO` or `FIXME` added by this change without an owner or an issue

### 11. Inconsistencies

Look for inconsistencies between comments and code:
- A docstring whose `Args`, `Returns` or `Raises` no longer matches the signature or the body
- Misleading variable names or comments
- Outdated comments after refactoring

### 12. Rule Document Validation

If the change touches `docs/code/` or `docs/__meta__/`, check the documents against their own format
contract: `docs/__meta__/code.md`, narrowed by the `code-<prefix>.md` specification for the document's
prefix. No checker is wired up, so this is done by reading.

## Notes

### Focus on Actionable Feedback

- Provide specific, actionable feedback on actual lines of code
- Avoid general comments without code references
- Reference specific file paths and line numbers
- Suggest concrete improvements

### Rule Compliance is Critical

Rule violations should be treated seriously as they:
- Reduce codebase consistency
- Make maintenance harder
- May introduce security vulnerabilities, in the code that parses documents from outside this repository
  above all
- Conflict with established architectural decisions

Always run the rule compliance review (section 6) as part of every code review.

### Review Priority

Sections are ordered by priority — review from top to bottom:
1. **Security concerns** (§1, highest priority)
2. **Principles violations** (§2)
3. **Potential bugs** and **unhandled failure paths** (§3–4)
4. **Backwards compatibility** (§5)
5. **Code rule violations** (§6)
6. **Testing** (§7)
7. **Performance** (§8)
8. **Documentation**, **dead code**, and **inconsistencies** (§9–11)

## Next Steps

After completing the code review:
1. Provide clear, prioritized feedback
2. Distinguish between blocking issues (bugs, security) and suggestions (style, performance)
3. Reference specific patterns from `docs/code/` when flagging violations
4. Suggest using `/code-format`, `/code-check`, and `/code-test` to validate fixes
