---
name: "test-functions"
description: "Inside the test function: Test<Subject> classes and test_<unit>_<condition>_<expectation> names, the mandatory Given/When/Then markers, one behaviour per test, assertion messages, fixture scope, pytest.raises on the class, parametrize over loops, and the sleep/network/order-dependence bans. Load when writing or reviewing a test function, naming a test, or adding a fixture"
type: "core"
scope: "global"
---

# Test Function Naming and Structure

A test's name is read far more often than its body — usually as a single red line in CI output, by someone who
has not opened the file. Everything in this document serves the moment that line is read: the name says what
broke, the assertion message says how, and the test's narrowness says where. Which tier a test belongs to,
which directory it lives in, and which markers select it are owned by
[test-organization](test-organization.md). This document owns what happens between `def` and the last
assertion, starting with the three markers ([§2](#2-given-when-then-with-markers)) that divide it.

## 1. `Test<Subject>` Classes, `test_<unit>_<condition>_<expectation>` Functions

Tests are grouped into classes named `Test<Subject>`, where the subject is the class, function, or behaviour
under test. Each test function is named `test_<unit>_<condition>_<expectation>`: what is being exercised, under
what circumstance, and what should happen.

The third segment is the one most often missing. A name that stops at the condition —
`test_check_with_empty_document` — tells a reader of the CI line that something about empty documents is wrong
but not whether the checker returned the wrong findings, returned none, or raised. The expectation is what
makes the failure legible without opening the file, and it is also what forces the author to decide what the
test is actually asserting before writing it.

`test_` at the start is pytest's collection requirement, not a description; the word "test" never appears
again in the name.

```python
# ❌ Bad — no expectation, so the CI line names a topic rather than a broken promise
@pytest.mark.unit
class TestChecker:
    def test_check_with_empty_document(self) -> None: ...
    def test_check_works(self) -> None: ...
    def test_test_check_heading_order(self) -> None: ...
```

```python
# ✅ Good — each name is a sentence about a promise, readable as a bare CI line
@pytest.mark.unit
class TestOutlineChecker:
    def test_check_with_empty_document_returns_no_findings(self) -> None: ...
    def test_check_with_missing_checklist_section_returns_one_finding(self) -> None: ...
    def test_check_with_headings_out_of_order_raises_value_error(self) -> None: ...
```

## 2. Given, When, Then, With Markers

Every test body is three labelled parts in order, marked `#: Given`, `#: When` and `#: Then`. The markers
are keyword-only: nothing follows the keyword on that line, and prose goes on the next line as an ordinary
comment.

**The form is chosen for grep and for tooling, not for decoration.** Keyword-only means one pattern matches
every marker and nothing else, and `#:` survives `ruff format` — which inserts a space after `#` unless the
next character is one of `" !:#'"` — while containing no regex metacharacter, so the pattern needs no
escaping:

```
^\s*#: (Given|When|Then)$
```

`#:` is also Sphinx's attribute-documentation comment, which is harmless here and worth knowing the shape
of: Sphinx reads a `#:` comment only above a module-level or class-level assignment, or above a `self.x`
assignment in a method. A marker above a local inside a test function is never one of those, and this
repository has no documentation toolchain at all. Keep the markers to test bodies and the two conventions
never meet.

| Marker | Holds |
|---|---|
| `#: Given` | Preconditions: locals bound from fixtures, constructed inputs, the literals the case turns on |
| `#: When` | **Exactly one** call — the thing under test, and nothing else |
| `#: Then` | Assertions, and the reads that observe a side effect of that call |

All three appear in every test, without exception. A test that constructs nothing still has a precondition, so
`#: Given` binds it to a named local: the empty string, the id, the value the case turns on. Naming it is what
leaves `#: When` holding the call alone, and what makes the scenario in the test's name findable in its body.

A second call under `#: When` means a failure names neither call. Logic under `#: Then` hides what is being
verified: a value transformed before it is asserted on is either setup, and belongs in `#: Given`, or evidence
that the test covers two behaviours ([§3](#3-one-behaviour-per-test)).

Three pytest idioms and where they fall:

- **`pytest.raises` straddles the split.** The `with pytest.raises(...) as exc_info:` block is the `When`,
  because the call under test sits inside it. Assertions about `exc_info.value` are `Then`.
- **`@pytest.mark.parametrize` is `Given` arriving through the signature.** The marker still appears in the
  body, over whatever the case binds locally.
- **A fixture argument is `Given` that already happened.** `#: Given` covers the locals derived from it, not
  the fixture's own setup.

```python
# ✅ Good — one call under When, and Then only asserts
def test_detailed_version_with_a_commit_reports_it_under_the_short_line(self) -> None:
    #: Given
    # a description as `git describe` returns it on a dirty tree
    commit = 'v0.1.0-2-g93b1ed1-dirty'

    #: When
    text = detailed_version(commit)

    #: Then
    assert text.splitlines()[1] == 'Commit:   v0.1.0-2-g93b1ed1-dirty'
```

```python
# ✅ Good — nothing to construct, so Given names the literal the case turns on
def test_register_with_a_name_already_taken_raises_duplicate_command_error(self) -> None:
    #: Given
    name = 'version'

    #: When
    with pytest.raises(DuplicateCommandError) as exc_info:
        register(name)(_other_handler)

    #: Then
    assert name in str(exc_info.value)
```

```python
# ❌ Bad — no markers, so setup, action and assertion are one undifferentiated block
def test_mount_adds_the_version_command(self) -> None:
    app = build_app()
    result = CliRunner().invoke(app, ['--help'])
    assert 'version' in result.output


# ❌ Bad — two calls under When, so a failure names neither of them
def test_version_command_matches_the_option(self) -> None:
    #: Given
    app = build_app()

    #: When
    from_option = runner.invoke(app, ['--version'])
    from_command = runner.invoke(app, ['version'])

    #: Then
    assert from_option.output == from_command.output


# ❌ Bad — the transformation under Then is setup, and it hides what is asserted
def test_detailed_version_reports_the_install_path(self) -> None:
    #: Given
    commit = None

    #: When
    text = detailed_version(commit)

    #: Then
    install_line = next(line for line in text.splitlines() if line.startswith('Install:'))
    assert install_line.split(':', 1)[1].strip().endswith('lorecraft')
```

## 3. One Behaviour Per Test

A test exercises one behaviour and asserts on it. Several assertions about that one behaviour are fine — a
returned report's finding count, its per-document breakdown, and its exit status are one outcome seen from
three angles. A second *behaviour*, exercised by a second call the test also cares about, is a second test.

pytest stops a test at its first failing assertion. When a test covers two behaviours, the second one is never
evaluated on the run that matters, and the failure names the test, which now names neither behaviour
accurately. A test called `test_writer_opens_and_writes_and_closes_succeeds` that goes red tells you only that
something in a third of the writer's lifecycle is broken.

```python
# ❌ Bad — three behaviours in one test; an open failure hides whether write or close work
@pytest.mark.unit
def test_report_writer_lifecycle_succeeds(tmp_path: Path) -> None:
    writer = ReportWriter(tmp_path / 'report.md')
    writer.open()
    assert writer.is_open
    written = writer.write_findings(make_findings(10))
    assert written == 10
    writer.close()
    assert not writer.is_open
```

```python
# ✅ Good — one behaviour each; a red line names the broken step
@pytest.mark.unit
class TestReportWriterLifecycle:
    def test_open_with_writable_path_opens_the_report(self, writer: ReportWriter) -> None:
        writer.open()
        assert writer.is_open, 'open should leave the writer open'

    def test_write_findings_with_ten_findings_reports_ten_written(self, open_writer: ReportWriter) -> None:
        written = open_writer.write_findings(make_findings(10))
        assert written == 10, f'expected 10 findings written, got {written}'
```

## 4. Assertions Carry a Message

Every `assert` carries a message saying what should have held. Where the actual value is small and not already
in the expression, the message interpolates it.

A bare `assert written == 10` fails with pytest's rewritten output, which shows the two values but not the
promise. `assert written == 10, 'every finding handed to the writer should be written'` fails with the promise, which
is what tells a reader whether the code or the expectation is wrong. On a boolean assertion the difference is
total: `assert result` fails with `assert False` and nothing else.

```python
# ❌ Bad — `assert False` in the log, and nobody knows what was supposed to be true
assert index.has_section('Checklist')
assert finding.line == 42
```

```python
# ✅ Good — the failure states the promise, and names the value that broke it
assert index.has_section('Checklist'), 'the outline index should carry every H2 the document declares'
assert finding.line == 42, f'the finding should point at the offending heading, got line {finding.line}'
```

## 5. Fixtures Declare Their Scope

Every `@pytest.fixture` states its scope explicitly, including `scope='function'`. A fixture that parses the
checked-in fixture corpus, compiles a JSON Schema, or builds a spec registry is `scope='session'` or
`scope='module'`; a fixture producing per-test state — a temp document, a findings list, a writer with its own
open file — is `scope='function'`.

Writing the default out loud is what makes the choice visible in review. The two failure modes are opposite
and both expensive: a corpus fixture left at function scope re-parses every fixture document once per test and
turns a two-second suite into two minutes, while a mutable fixture promoted to session scope leaks state
between tests and produces the order-dependent failures
[§8](#8-forbidden--sleeping-real-network-order-dependence) bans.

A session-scoped fixture yields something **immutable or externally reset**: the parsed corpus is shared, but
each test writes its own document under its own temp directory.

```python
# ❌ Bad — scope unstated, so every fixture document is re-parsed per test, and the shared
# findings list is mutated by whichever test ran first
@pytest.fixture
def fixture_corpus():
    return load_corpus(FIXTURE_ROOT)


@pytest.fixture(scope='session')
def draft_findings() -> list[Finding]:
    return make_findings(3)
```

```python
# ✅ Good — expensive and immutable at session scope, per-test state at function scope
@pytest.fixture(scope='session')
def fixture_corpus() -> Corpus:
    return load_corpus(FIXTURE_ROOT)


@pytest.fixture(scope='function')
def draft_document(tmp_path: Path) -> Iterator[Path]:
    path = tmp_path / f'draft-{uuid4().hex}.md'
    path.write_text(MINIMAL_RULE_DOCUMENT, encoding='utf-8')
    yield path
    path.unlink()
```

## 6. `pytest.raises` Matches the Exception Class, Not the Message

A test asserting a failure matches the exception **class**. `match=` is used only for a value the contract
actually promises — a field the exception is required to name, a bound it is required to report — and never
for the sentence around it.

An exception message is prose. It gets reworded for clarity, translated into a better error, or given more
context, and none of those are behaviour changes. A suite that string-matches on messages goes red on every
one of them, and the reflex that follows — paste the new wording into the test — means the test now asserts
whatever the code currently says, which is no assertion at all. Match the class, and if the class is too
coarse to distinguish two failures, the fix is a more specific exception type
([python-exceptions](python-exceptions.md)), not a regex.

```python
# ❌ Bad — couples the suite to wording no contract promises; reflowing the message breaks it
with pytest.raises(FrontmatterSchemaError, match="Field 'scope': expected 'global', the document said 'package'"):
    check_frontmatter(document, schema)
```

```python
# ✅ Good — the class is the contract
with pytest.raises(FrontmatterSchemaError):
    check_frontmatter(document, schema)
```

```python
# 🔶 Acceptable — the offending field name is part of the promised contract, so match that and
# nothing else about the sentence
with pytest.raises(FrontmatterSchemaError, match='scope'):
    check_frontmatter(document, schema)
```

## 7. Parametrize Instead of Looping

A test covering several inputs uses `@pytest.mark.parametrize`. A `for` loop over cases inside a test body is
not written.

A loop collapses N cases into one test. It stops at the first failing case, so a run reports one failure when
five are broken and reveals the remaining four only after four more fix-and-rerun cycles. The CI line names
the test, not the case, so nobody knows which input failed without reading the traceback. Parametrized cases
are N independent tests: all five fail, each names its own input, and `-k` can select one.

Give each case an `id` when the values do not read clearly on their own.

```python
# ❌ Bad — one test, first failure hides the rest, and the CI line names no input
@pytest.mark.unit
def test_section_counts_are_correct() -> None:
    for text, depth, expected in [(THREE_SECTIONS, 2, 3), (NO_HEADINGS, 2, 0), (NESTED_SECTIONS, 3, 5)]:
        assert len(split_sections(text, depth)) == expected
```

```python
# ✅ Good — three independent tests, each naming its own case in the CI line
@pytest.mark.unit
@pytest.mark.parametrize(
    ('document_text', 'heading_depth', 'expected_sections'),
    [
        pytest.param(THREE_SECTIONS, 2, 3, id='three-top-level-sections'),
        pytest.param(NO_HEADINGS, 2, 0, id='document-without-headings'),
        pytest.param(NESTED_SECTIONS, 3, 5, id='nested-subsections'),
    ],
)
def test_split_sections_with_varied_documents_returns_expected_section_count(
    document_text: str, heading_depth: int, expected_sections: int
) -> None:
    sections = split_sections(document_text, heading_depth)
    assert len(sections) == expected_sections, f'expected {expected_sections} sections, got {len(sections)}'
```

## 8. Forbidden — Sleeping, Real Network, Order Dependence

Three things are never written in a test, in any tier.

- **`time.sleep` as a synchronisation device.** A sleep is a guess about someone else's timing: too short and
  the test is flaky under CI load, too long and it taxes every future run forever. Wait on the condition —
  join the thread that writes the report, drain the finding queue, assert on the file only after the writer's
  `close()` has returned.
- **A real network call to a service the test did not start.** A schema URL fetched over HTTP, a documentation
  site, or anyone's live API makes the suite fail for reasons unrelated to the diff and couples green CI to
  someone else's uptime. A test that needs a remote schema resolves it from the checked-in copy instead.
- **A dependency on test order.** A test that passes only after another test ran — because that one wrote the
  document, seeded the fixture directory, or left the module-level registry populated — is a test that fails
  when run alone, which is exactly how someone will run it while debugging. Every test creates what it needs
  and removes it, or gets it from a fixture that does.

```python
# ❌ Bad — a sleep guessing at the writer thread, a spec fetched from a live host, and a fixture
# directory this test relies on a sibling having populated
@pytest.mark.unit
def test_corpus_check_reports_every_finding() -> None:
    writer_thread.start()
    time.sleep(5)
    spec = load_spec('https://specs.example.com/rule-document.json')
    findings = check_corpus(SHARED_FIXTURE_DIR, spec)   # populated by an earlier test in this file
    assert len(findings) == 12, 'every malformed document should be reported'
```

```python
# ✅ Good — the writer is joined by the fixture, the spec is the checked-in copy, and the
# corpus is this test's own
@pytest.mark.unit
def test_check_corpus_with_twelve_malformed_documents_reports_twelve_findings(
    malformed_corpus: Path, bundled_spec: FormatSpec
) -> None:
    findings = check_corpus(malformed_corpus, bundled_spec)
    assert len(findings) == 12, f'every malformed document should be reported, got {len(findings)}'
```

## Checklist

Before committing code, verify:

- [ ] Every test sits in a `Test<Subject>` class named for what is under test
- [ ] Every test function name has all three segments: unit, condition, and expectation
- [ ] No test name contains "test" after the mandatory `test_` prefix
- [ ] No test exercises a second behaviour it also asserts on — those are two tests
- [ ] Every `assert` in the diff carries a message stating the promise
- [ ] Every `@pytest.fixture` states `scope=` explicitly, including `scope='function'`
- [ ] No session- or module-scoped fixture yields mutable per-test state
- [ ] Every `pytest.raises` matches an exception class
- [ ] No `match=` asserts on message wording — only on a value the contract promises
- [ ] No `for` loop over test cases inside a test body; `@pytest.mark.parametrize` is used
- [ ] No `time.sleep` is used to wait for anything
- [ ] No test calls a network service it did not start, or that a fixture did not provision
- [ ] Every test creates the documents, fixture directories, and registry entries it needs and cleans them up

## References

- [test-organization](test-organization.md) - Related: Owns the tier, the directory, and the markers that select the test this document governs the inside of
- [python-exceptions](python-exceptions.md) - Related: Owns the exception types `pytest.raises` matches on, and the granularity that makes `match=` unnecessary
- [python-naming](python-naming.md) - Related: Owns the naming rules the three-segment test name specialises
- [pattern-resource-lifecycle](pattern-resource-lifecycle.md) - Related: Owns the acquire/release contract a scoped fixture mirrors
- [principle-single-responsibility](principle-single-responsibility.md) - Foundation: One behaviour per test, for the same reason as one reason to change per class
- [principle-least-surprise](principle-least-surprise.md) - Foundation: A failing test should say what it expected without being opened

## External References

- [pytest — How to parametrize fixtures and test functions](https://docs.pytest.org/en/stable/how-to/parametrize.html)
- [pytest — Fixture scopes](https://docs.pytest.org/en/stable/how-to/fixtures.html#scope-sharing-fixtures-across-classes-modules-packages-or-session)
- [pytest — Assertions about expected exceptions](https://docs.pytest.org/en/stable/how-to/assert.html#assertions-about-expected-exceptions)
