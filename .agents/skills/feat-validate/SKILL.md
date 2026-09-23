---
name: feat-validate
description: Verify feature doc alignment with implementation. Use when asking about feature implementation status, or to check that documented functionality exists in code and has test coverage
compatibility: Requires the feature corpus in docs/feat/ and the checker sources in src/lorewright/. Reads code and tests; runs only the repository's own gates through just.
allowed-tools: Read Grep Glob Bash(just typecheck *) Bash(just test-unit *) Bash(just test *)
---

# Feature Validate Skill

This skill verifies that documented functionality is actually implemented in the codebase and that the
implementation aligns with what's documented. It also checks for test coverage and warns about untested
functionality.

`docs/feat/` is empty today and the checker package holds only `__init__.py`, so there is nothing to validate
yet. The moment a feature doc lands, this is the skill that keeps it honest.

## When to Use This Skill

Verifies a feature doc against the code: does the documented behaviour actually exist, and is it tested?
For the *declared* maturity of a feature, which is a frontmatter field rather than a fact about the code,
use `/feat-status`. For whether the doc has the right frontmatter, sections and length — its **form** rather
than its **truth** — use `/docs-rules-check`, which runs the checks `just check-docs` wires up.

Use this skill when:
- User explicitly asks to verify a feature doc against implementation
- Auditing existing feature docs for accuracy
- Checking if documented functionality has test coverage
- Validating that code matches what's documented

## Verification Scope

Features can be implemented in many forms - not just functions. Verify ALL documented capabilities:

### Types of Documented Functionality

| Type | Examples | What to Verify |
|------|----------|----------------|
| **Functions/Methods** | Frontmatter parser, budget counter | Signature, args, return type |
| **CLI surfaces** | A check script's flags, its exit codes | Flag names, defaults, exit status |
| **Spec dialects** | Frontmatter schema keys, section-outline rules | Which rules the checker actually enforces |
| **Reporter contracts** | Text and JSON finding output | Field names, severity vocabulary, stream |
| **Data flows** | Corpus discovery → parse → check → report | Components involved, data transformations |
| **Configuration** | `pyproject.toml` settings, spec file locations | Config keys, defaults, validation |
| **Components** | Checker modules, the check registry | Initialization, lifecycle, interactions |

### 1. Functionality Verification

Each capability described in the doc MUST exist in production code:
- Documented components must exist in the codebase
- Documented behaviors must match actual implementation
- Documented data flows must be traceable through components
- Documented constraints and limitations must be enforced

### 2. Production Code Review

- Locate implementation files from Architecture/Implementation section
- Verify documented modules/flags/functions exist
- Check that documented behavior matches implementation
- Verify documented interactions between components are accurate

### 3. Test Coverage Review

- Search `tests/unit/` for tests covering documented functionality
- Search for tests that exercise a documented end-to-end scenario against a checked-in fixture document
- Assess if existing tests cover happy path and critical corner cases
- Suggest specific test enhancements when gaps are found

### Test Coverage Philosophy: "Just the Right Amount"

Aim for sufficient coverage without over-testing:

**Must Have (HIGH priority)**:
- Happy path for each documented capability
- Error handling for documented failure modes
- Critical corner cases mentioned in Limitations section

**Should Have (MEDIUM priority)**:
- Edge cases for documented parameters (missing key, empty document, boundary values)
- Integration points between documented components

**Not Required**:
- Exhaustive permutation testing
- Trivial variations of already-covered scenarios
- Implementation details not exposed in documentation

### 4. Misalignment Detection

- Flag documented features that don't exist in code
- Flag implemented features that behave differently than documented
- Flag missing test coverage for documented scenarios

## Verification Workflow

### Step 1: Parse Feature Doc

Extract from the feature doc:
- Documented capabilities from the Usage section (functions, flags, behaviors)
- Component interactions from the Architecture section
- Documented constraints and limitations
- File paths from the Architecture/Implementation section

`docs/__meta__/feat.md` fixes which sections a doc of each type carries, so read it when a section you expect
is absent: a `meta` doc has no Usage section by design, and its concrete usage lives in its children.

### Step 2: Verify Production Code

1. Read implementation files listed in Architecture/Implementation
2. Match documented capabilities to actual implementations
3. For a capability spread across modules, trace the flow through every component it names
4. Check documented constraints are enforced

**What to verify by type**:

**For functions**:
- Does the function exist with documented signature?
- Do parameter types match?
- Does return type match?

**For CLI surfaces**:
- Does the flag exist with the documented name and default?
- Does the script exit with the documented status — 0 clean, 1 findings, 2 usage error?
- Do the positional paths and the root-discovery behaviour match the doc?

**For spec dialects**:
- Does the checker enforce every rule the doc claims it enforces?
- Are the documented severities the ones the code emits?
- Does a rule the doc does not mention get enforced anyway?

**For reporter contracts**:
- Do the documented output fields exist with those names?
- Does the documented format flag produce that format?
- Do findings go to the documented stream?

**For data flows**:
- Do documented components exist?
- Is the documented flow accurate?
- Are transformations implemented as described?

**For configuration**:
- Do documented config keys exist?
- Are documented defaults accurate?
- Is validation implemented as described?

**Use the repository's own gates as evidence, not as a substitute for reading:**
- `just typecheck` — a documented symbol that does not resolve, or resolves with a different signature, shows
  up here rather than at runtime.
- `just test-unit` — run it when you have found the tests that cover the documented behaviour, so the report
  says the tests *pass*, not merely that they exist.

Do not claim a capability is verified because a gate is green. A gate proves the code type-checks and the
existing tests pass; only reading the implementation proves it does what the doc says.

### Step 3: Review Test Coverage

Search the codebase for tests that exercise documented functionality:

1. **Unit tests**: Search `tests/unit/` for the module, function and finding names the doc uses
2. **Fixture-backed tests**: Search for tests that feed a checked-in document fixture through the documented
   check and assert on the findings
3. **Scenario tests**: Search for tests that exercise the documented flow end to end

**Use Grep tool** to search for:
- Key identifiers documented in the feature
- Component names and interactions
- Test functions that reference the implementation

### Step 4: Generate Report

Produce a structured report listing:
- Verified functionality (docs match implementation)
- Misalignments (docs don't match implementation)
- Test coverage status per documented feature
- Warnings for untested functionality

## Report Format

```markdown
## Feature Implementation Verification: <filename>

### Functionality Verification

| Documented Capability | Implementation | Status |
|-----------------------|----------------|--------|
| Frontmatter checked against the header schema | `checks/header.py:check()` | ✅ VERIFIED |
| Flow: discover corpus → parse → validate → findings | Multiple modules | ✅ VERIFIED |
| Flag `--format json` emits machine-readable findings | `cli.py:build_parser()` | ✅ VERIFIED |
| Findings carry path, line, rule id and message | `finding.py:Finding` | ✅ VERIFIED |
| Flag `--root` overrides repository-root discovery | NOT FOUND | ❌ MISSING |

### Test Coverage

| Documented Capability | Tests Found | Status |
|-----------------------|-------------|--------|
| Valid document reports no findings | Yes | ✅ COVERED |
| Missing required key reports a finding | Yes | ✅ COVERED |
| Unreadable schema file | No | ⚠️ NO TESTS |

### Suggested Test Enhancements

⚠️ **Missing critical test coverage**:

| Priority | Scenario | Type | Rationale |
|----------|----------|------|-----------|
| ⚠️ HIGH | Unreadable schema file | Corner case | Documented but untested |
| ⚠️ HIGH | Malformed YAML frontmatter | Happy path | Core error handling |
| MEDIUM | Document with empty frontmatter block | Corner case | Boundary condition |

### Misalignments Found

1. **MISSING IMPLEMENTATION**: `--root` override is documented but never parsed
2. **BEHAVIOR DIFFERENCE**: Docs say a malformed document exits 2, but the code exits 1
3. **CONFIG MISMATCH**: Default prose budget is 400 words, not 500 as documented

### Verdict: PASS/FAIL
- Misalignments found: X
- ⚠️ Test coverage warnings: Y (missing critical tests)
```

## Verification Notes

### What to Check in Production Code

Depends on the type of documented capability:

1. **Components & modules**
   - Does the module exist in the documented location under `src/lorewright/`?
   - Are documented entry points implemented?
   - Do component interactions match documentation?

2. **CLI surfaces & reporters**
   - Does the flag exist with the documented name, default and help text?
   - Does the output format match the documented finding fields?
   - Are the documented exit codes returned?

3. **Data flows**
   - Can you trace the documented flow through code?
   - Are all documented transformations implemented?
   - Do components interact as described?

4. **Configuration**
   - Do documented config keys exist?
   - Are defaults accurate?
   - Is validation implemented?

### What to Check in Tests

Evaluate test coverage against the "Just the Right Amount" philosophy:

**For each documented capability, check:**
- Is there a happy path test? (HIGH priority if missing)
- Are documented error cases tested? (HIGH priority if missing)
- Are Limitations section corner cases tested? (HIGH priority if missing)
- Are parameter edge cases tested? (MEDIUM priority if missing)

**When suggesting enhancements:**
- Be specific about the scenario to test
- Classify as happy path or corner case
- Explain why it matters (e.g., "documented error handling", "boundary condition")

A unit test only runs in `just test-unit` if it carries the `unit` marker, so a test without the marker is a
coverage gap for that tier even when it exists. Note it as one.

### Enhancement Priority Criteria

**⚠️ HIGH Priority** - Issue WARNING, suggest immediately:
- No happy path test for a documented capability
- Documented error handling has no test
- Critical corner case from Limitations section untested

**MEDIUM Priority** - Suggest as improvement:
- Edge cases for optional parameters
- Boundary value testing
- Integration between documented components

**LOW Priority** - Note but don't emphasize:
- Additional variations of covered scenarios
- Non-critical edge cases

**Note**: Missing HIGH priority tests should always trigger a ⚠️ WARNING in the report.

## Pre-approved Commands

These tools/commands can run without user permission:
- Read tool for feature docs and source files
- Grep tool for searching implementations and tests
- Glob tool for finding files
- `just typecheck` to confirm documented symbols resolve with the documented signature
- `just test-unit`, or `just test` when the feature spans tiers, to confirm the tests you found pass

## Example Verification Sessions

### Example 1: Header Check Feature (Function-focused)

**Scenario**: Verify `docs/feat/check-header.md`

1. **Parse doc** - Extract documented capabilities:
   - `check_header(document, schema)` function signature
   - Returns a list of findings carrying `path`, `line`, `rule` and `message`
   - Enforces the required keys, the quoting rule, and `name` matching the filename

2. **Verify implementation** - Read files from the Implementation section:
   - Verify the function exists with the correct signature
   - Verify the finding type matches the documented fields
   - Verify each of the three documented rules is actually enforced
   - Run `just typecheck` to catch a documented signature the code no longer has

3. **Search for tests** - Check coverage:
   - Grep `tests/unit/` for the function and finding names
   - Check which documented rules have a fixture-backed test
   - Run `just test-unit` to confirm those tests pass

4. **Generate report** with findings

### Example 2: Reporter Contract Feature (Multi-component)

**Scenario**: Verify `docs/feat/report-json.md`

1. **Parse doc** - Extract documented capabilities:
   - `--format json` accepted by every check script
   - Flow: findings collected → serialized → written to stdout, one JSON array
   - Documented field names and severity vocabulary
   - Exit codes: 0 clean, 1 findings, 2 usage error

2. **Verify implementation** - Trace through components:
   - Check the flag is parsed by each script the doc names
   - Verify the serializer emits the documented field names
   - Check the severity values the code can produce against the documented set
   - Verify the exit codes match

3. **Search for tests** - Check coverage:
   - Grep for tests asserting on the JSON payload
   - Check exit-code tests exist for all three documented statuses

4. **Generate report** with findings

## Next Steps

After verification:

1. **If misalignments found** - Either fix the docs or fix the implementation
2. **If test coverage warnings** - Consider adding tests or documenting the gap
3. **If all passes** - Feature doc is verified and ready for commit
