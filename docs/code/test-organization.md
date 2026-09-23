---
name: "test-organization"
description: "Test tiers and their directories, the one mandatory tier marker per test, marker declaration under --strict-markers, what a unit test may not depend on or mock, and the shared contract suite a new checker passes first. Load when adding a test file, choosing where a test belongs, introducing a marker, or adding a new checker"
type: "core"
scope: "global"
---

# Test Tier Organization

A test's directory says what it needs to run, and its marker says the same thing to pytest. Those two facts
must agree, because the directory is what a reader selects on and the marker is what `just` and CI select on,
and a test whose marker disagrees with its directory runs in a suite that cannot satisfy it. Everything inside
a test function — its name, its structure, its assertions, its fixtures — is owned by
[test-functions](test-functions.md). This document owns where a test lives and what selects it.

## 1. One Tier, One Directory

| Directory | Needs to run | Typical duration | Purpose |
|---|---|---|---|
| `tests/unit/` | Nothing beyond the interpreter | Milliseconds | Pure logic: frontmatter parsing, outline matching, length budgets, spec loading |

**There is exactly one tier today**, and `just test-unit` is what selects it. A test that needs a network
service, a subprocess, or a writable path outside a temp directory has no directory to live in yet, and
putting it under `tests/unit/` does not give it one — it gives the unit suite a failure nobody can reproduce
without the missing dependency.

A tier is not free. It needs a directory, a marker declared in `[tool.pytest.ini_options]`, and a gate that
runs it, and all three land in the same change or the tier is a directory nothing executes. Add one when a
behaviour genuinely cannot be observed at the tier below — not because a test was awkward to write at that
tier.

Choose the cheapest tier that can actually observe the behaviour, and push logic down into a shape a unit test
can reach rather than reaching up for a tier that can test it as written. A checker that takes a parsed
document and returns findings is reachable from `tests/unit/`; the same checker reading its input from a live
HTTP endpoint is not, and the fix is the seam, not the tier.

## 2. Every Test Carries Exactly One Tier Marker

Every test function or test class carries exactly one tier marker — today that is `@pytest.mark.unit` — and it
matches the directory the test lives in.

Directory placement alone selects nothing: `just test-unit` and CI jobs select on markers, so an unmarked test
is a test that runs in no gate and fails in none. A second tier marker is worse than none: today it names a
tier that does not exist, so `--strict-markers` aborts the whole run at collection; once a second tier does
exist, the test runs in both suites and the cheaper one fails for want of what it cannot provide.

```python
# ❌ Bad — no tier marker, so this runs only when someone happens to invoke the file by path
class TestSectionSplitting:
    def test_split_sections_at_h2_yields_one_span_per_heading(self) -> None: ...
```

```python
# ❌ Bad — a second tier marker naming a tier this project does not have; collection aborts
@pytest.mark.unit
@pytest.mark.integration
def test_outline_checker_reads_spec_from_disk() -> None: ...
```

```python
# ✅ Good — one marker, on the class, matching `tests/unit/`
@pytest.mark.unit
class TestSectionSplitting:
    def test_split_sections_at_h2_yields_one_span_per_heading(self) -> None: ...
```

## 3. Every Marker Used Is Declared

Every marker a test carries appears in the `markers` list under `[tool.pytest.ini_options]`, with a
description saying what it selects. `--strict-markers` is enabled for this project.

That flag turns an undeclared marker into a **collection error**, not a warning: the run stops before a single
test executes. The consequence worth internalising is the inverse one, and it is the quiet one — a `just`
recipe or CI job whose `-m` expression names a marker nobody declared **fails at collection** rather than
skipping politely. A typo'd selector does not silently run zero tests and report green; it errors. Read the
collection error as a declaration bug, not a test bug.

```python
# ❌ Bad — the marker was never added to pyproject; collection aborts the entire run
@pytest.mark.corpus
def test_check_corpus_reports_one_finding_per_document() -> None: ...
```

```toml
# ✅ Good — declared with what it selects, so `-m corpus` is a real selector
markers = [
    "unit: Unit tests (fast, no external dependencies)",
    "corpus: Tests that read the checked-in document corpus",
]
```

## 4. A Unit Test Has No External Dependency and Does Not Mock Its Subject

A unit test touches no network, no database, no subprocess, and no filesystem beyond a temp directory and the
checked-in fixture documents. It also does not mock the thing it is testing, and does not patch module
internals to reach its assertion.

**This narrows the blanket rule, deliberately.** A standing instruction that unit tests must not mock at all
is easy to state and easy to break, and a rule broken a third of the time is worse than no rule: it stops
being a check and becomes something reviewers apologise for. The honest line, and the one this section
enforces, is drawn around **what** is mocked rather than **whether** mocking appears:

- **Not the subject.** Patching the class or function under test, or patching a module-internal symbol to
  steer it, means the test asserts against the patch. It passes when the production code is deleted.
- **Not an unspecified stand-in.** A bare `Mock()` or `MagicMock()` standing in for a collaborator answers
  every attribute access with another mock. The test then asserts against a shape **no production class has to
  honour** — rename the collaborator's method and the mock happily accepts the old name forever, while the real
  call site breaks.
- **A hand-written fake is fine.** A small real class implementing the collaborator's real contract, readable
  top to bottom, is a legitimate unit-test collaborator. It is code, so it breaks when the contract changes,
  which is exactly the property a `MagicMock` lacks.

A test that genuinely needs a live service is not a unit test with a mocking problem. It is a test for a tier
this project does not have, and the fix is to make the logic reachable without the service
([§1](#1-one-tier-one-directory)), not to mock the service away.

```python
# ❌ Bad — `MagicMock` accepts any call, so this passes even after `check_document` is renamed
# to `check`, and every real call site has broken
@pytest.mark.unit
def test_check_corpus_checks_every_document() -> None:
    checker = MagicMock()
    check_corpus(checker, documents=make_documents(3))
    assert checker.check_document.call_count == 3
```

```python
# ✅ Good — a fake with a real, readable contract; renaming the method breaks this test,
# which is the whole point of having it
class FakeChecker:
    """In-memory checker recording every document it was given."""

    def __init__(self) -> None:
        self.documents: list[RuleDocument] = []

    def check_document(self, document: RuleDocument) -> list[Finding]:
        self.documents.append(document)
        return []


@pytest.mark.unit
def test_check_corpus_forwards_every_document_to_the_checker() -> None:
    checker = FakeChecker()
    check_corpus(checker, documents=make_documents(3))
    assert len(checker.documents) == 3, 'every document should reach the checker'
```

## 5. A New Checker Gets the Shared Suite Before It Gets Bespoke Tests

A new checker's first test file subclasses the shared checker suites and supplies the checker's test
configuration — the conforming document, the violating document, the spec it reads, the findings it is
expected to produce. Only once those pass does the checker get tests written specifically for it.

The shared suite is the executable definition of what "a checker" means: it returns findings rather than
raising, every finding carries a line, a conforming document yields none, and an empty file is a finding
rather than a crash. A checker that passes bespoke tests but not the shared suite is a checker that satisfies
its author's idea of the contract and not the one the report relies on. Running the shared suite first also
means the bespoke tests that follow are about what is genuinely unusual — a heading-numbering rule, a budget
measured in prose lines, a fix the checker can apply itself — instead of re-testing the common contract in a
seventh dialect.

```python
# ✅ Good — the shared contract first; the bespoke class holds only what is unique to this checker
class OutlineCheckerTestConfig(CheckerTestConfig):
    checker_class = OutlineChecker
    spec_fixture_name = 'outline_spec'

    def make_conforming_document(self) -> RuleDocument: ...
    def make_violating_document(self) -> RuleDocument: ...


@pytest.mark.unit
class TestOutlineCheckerContract(BaseCheckerTests):
    config = OutlineCheckerTestConfig()


@pytest.mark.unit
class TestOutlineCheckerReporting(BaseReportingTests):
    config = OutlineCheckerTestConfig()
```

## 6. Requirement Markers Are Additive and Independent of Tier

A requirement marker names what the test needs — the checked-in corpus, a particular fixture tree — and stacks
on top of the tier marker rather than replacing it. A test can be selected by tier, by requirement, or by
both, and the two axes never collide.

This is what lets a contributor narrow a run at all: the tier marker answers "how expensive is this", the
requirement marker answers "what must be present", and only their intersection has to be satisfiable. A
requirement marker used **instead of** a tier marker removes the test from every tier gate, and it stops
running in CI without anyone noticing, because the requirement suite that does select it is often conditional.

```python
# ❌ Bad — requirement marker only; `just test-unit` does not select this, and nothing else does
@pytest.mark.corpus
def test_check_corpus_over_fixture_tree_reports_one_finding_per_document() -> None: ...
```

```python
# ✅ Good — both axes, so `-m unit`, `-m corpus`, and `-m 'unit and corpus'` all find it
@pytest.mark.unit
@pytest.mark.corpus
def test_check_corpus_over_fixture_tree_reports_one_finding_per_document() -> None: ...
```

## Checklist

Before committing code, verify:

- [ ] Every new test file is under `tests/unit/`, or under a tier directory introduced in the same change as
      its marker and its gate
- [ ] Each test's directory matches what it actually needs: no network, no subprocess, and no writable path
      outside a temp directory under `tests/unit/`
- [ ] Every new test carries exactly one tier marker — `@pytest.mark.unit` today
- [ ] Every marker used in the diff appears in the `markers` list under `[tool.pytest.ini_options]`
- [ ] Every `-m` expression added to a `just` recipe or CI job names only declared markers — an undeclared one
      is a collection error, not a skip
- [ ] No test under `tests/unit/` opens a socket, spawns a subprocess, or writes outside a temp directory
- [ ] No unit test patches its own subject or a module-internal symbol
- [ ] No unit test passes a bare `Mock()` or `MagicMock()` as a collaborator; a hand-written fake class is
      used instead
- [ ] A new checker's tests subclass the shared checker and reporting suites before any bespoke test is added
- [ ] Every requirement marker sits alongside a tier marker, never instead of one

## References

- [test-functions](test-functions.md) - Related: Owns everything inside the test function — naming, one behaviour per test, assertions, fixtures, parametrization
- [pattern-registry](pattern-registry.md) - Related: Owns the checker registry whose every entry the shared suite is run against
- [pattern-resource-lifecycle](pattern-resource-lifecycle.md) - Related: Owns the acquire/release contract a scoped fixture drives
- [logging](logging.md) - Related: Owns the log lines a failing test is read through
- [principle-single-responsibility](principle-single-responsibility.md) - Foundation: One tier per test, because one test answers one kind of question

## External References

- [pytest — Working with custom markers](https://docs.pytest.org/en/stable/example/markers.html)
- [pytest — `--strict-markers`](https://docs.pytest.org/en/stable/how-to/mark.html)
- [Martin Fowler — Test Double](https://martinfowler.com/bliki/TestDouble.html)
