---
name: "tests-assertions"
description: "What a test's Then block asserts and how: a message stating the promise on every assert, the whole returned value compared to an expected one, a projection only when the sequence is the fact, one assert per fact up to three and all/any beyond, is for identity, and pytest.raises on the class with the message checked only for the values it names. Load when writing or reviewing the assertions of a test, or an assertion message"
type: "core"
scope: "global"
---

# Test Assertions

A test fails at an assertion, and the assertion is all the reader of the CI line gets: the expression pytest
rewrites, and the message the author wrote. This document owns that line — what each `assert` under `#: Then`
checks and what it says when it fails. The `#: Then` block itself, and the rule that a test covers one
behaviour, are owned by [tests-functions](tests-functions.md).

## 1. Assertions Carry a Message

Every `assert` carries a message stating the promise: what should have held, and where it is not obvious, why.
Where the actual value is small and not already in the expression, the message interpolates it, after the
promise: `f'..., got {written}'`.

A bare `assert written == 10` fails with pytest's rewritten output, which shows the two values but not the
promise. On a boolean assertion the difference is total: `assert result` fails with `assert False` and nothing
else. The promise is what tells a reader whether the code or the expectation is wrong.

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

```python
# 🔶 Acceptable — a guard on a command's exit status, before the assertions that state the promise, may carry
# the command's output alone: the status explains nothing, and the output is what explains the failure
assert result.exit_code == 0, result.output
assert result.stdout == expected, 'the root help matches the reviewed snapshot'
```

## 2. Compare the Whole Value

Name the result under `#: When` and compare it, whole, to an expected value built in the test: a tuple of the
value objects the code should return, a schema, an empty tuple for a clean result. Comparing the whole value
is one fact, however many fields it has.

The expected value reads like the output it stands for, and pytest diffs a dataclass field by field, so a red
line shows exactly which field moved. Nothing the code returned escapes the comparison, so a field nobody
thought to check cannot change unnoticed.

```python
# ✅ Good — the expected occurrences read like the output, and a mismatch is diffed field by field
assert occurrences == (
    DuplicateKey(spec=SPEC, line=LineNumber.from_int(3), key='name', first_line=LineNumber.from_int(2)),
), 'a key written twice is one occurrence, on the line that repeats it'
assert report.diagnostics == (), 'a document that conforms to its specifications carries no diagnostic'
```

## 3. Project Only When the Sequence Is the Fact

Project the result into a list only when the projected sequence is itself what the test is about: which rules
fired, in what order, across several items. A projection of one field, or of the fields an ordering is
decided on, states that fact in one literal.

A projection built for a single item, or of fields the test is not about, is a compound comparison: compare
the whole value ([§2](#2-compare-the-whole-value)) or unfold it ([§4](#4-one-fact-per-assertion)).

```python
# ✅ Good — the order across several diagnostics is the fact, and the projection states it in one literal
assert [
    (diagnostic_order(diagnostic).location, str(diagnostic.occurrence.CODE)) for diagnostic in report.diagnostics
] == [(1, 'OUT005'), (5, 'OUT004')], 'diagnostics are ordered by line, then by code'
```

## 4. One Fact Per Assertion

Each `assert` checks one fact, with the message for that fact. A value built under `#: Then` only so that
several facts compare at once — a tuple of fields projected from one item — is unfolded into one `assert` per
fact, ordered so each guards the next: the count before the item it indexes, the type before a field only that
type carries.

A compound comparison hides which fact broke: the reader diffs two nested literals to learn whether the count,
the type or the text is wrong, and one message has to cover all three. Unfolded, the first failing `assert`
names the fact.

Unfold up to three facts about the same subject. When one fact holds of more items than that, assert it once
over all of them with `all()` or `any()`, and interpolate the items into the message, so the failure shows
which of them broke it.

```python
# ❌ Bad — a failure prints two nested literals, and one message covers the count, the type and the text
errors = [(error['type'], error['msg']) for error in exc_info.value.errors()]
assert errors == [('string_type', 'Input should be a valid string')], f'a number is not text, got {errors}'
```

```python
# ✅ Good — the first failing assert names the fact that broke, and says what it promised
errors = exc_info.value.errors()
assert len(errors) == 1, f'one error is reported, got {errors}'
assert errors[0]['type'] == 'string_type', 'a number is not text'
assert errors[0]['msg'] == 'Input should be a valid string', 'the message is the one pydantic gives'
```

```python
# ✅ Good — one fact over every skill, and the failure shows each skill with the errors it carries
assert all(not errors for errors in schema_errors.values()), (
    f'every skill follows the specification, so the schema must accept them: {schema_errors}'
)
```

## 5. `is` for Identity

Compare with `is` where the promise is identity rather than equality: an enum member, `None`, the very object
passed in coming back unchanged, an error's cause being its source. `==` would pass for an equal copy, which is
not what the test promised.

```python
# ✅ Good — the same object, not an equal one
assert returned is FRONTMATTER_CHECK, 'registration returns the check unchanged, so it can be bound to a name'
assert exc_info.value.refusal is OsRefusal.PERMISSION_DENIED, 'a locked parent is a refused permission'
```

## 6. A Raised Error: the Class, Then What It Carries

A test asserting a failure matches the exception **class** in `pytest.raises`, then asserts the data the error
carries — the rejected value, its source, its cause — each with its own `assert`.

An exception message is prose around values. It gets reworded for clarity or given more context, and none of
those are behaviour changes. Assert the **values** the message promises to name — a path, a bound, a field —
with `in`, and never a word of the sentence around them, neither with `in` nor with `match=`. A class too
coarse to tell two failures apart calls for a more specific exception type ([error-types](error-types.md)),
not a regex.

```python
# ❌ Bad — couples the suite to wording no contract promises; reflowing the message breaks it
with pytest.raises(FrontmatterSchemaError, match="Field 'scope': expected 'global', the document said 'package'"):
    check_frontmatter(document, schema)
assert 'empty' in str(exc_info.value), 'the blank name is reported'
```

```python
# ✅ Good — the class is the contract, then the data it carries, then the value its message names
with pytest.raises(UnreadableDocumentError) as exc_info:
    read_document(path)

assert exc_info.value.path == path, 'the error keeps the document it could not read'
assert exc_info.value.source is exc_info.value.__cause__, 'the decoder failure is the cause'
assert str(path) in str(exc_info.value), 'the message names the document'
```

## Checklist

Before committing code, verify:

- [ ] Every `assert` carries a message stating the promise; only an exit-status guard may carry the output alone
- [ ] A returned value is compared whole to an expected value wherever the test is about all of it
- [ ] A projection appears only where the projected sequence across several items is the fact
- [ ] No `assert` compares a tuple of fields projected from one item; each fact has its own `assert`
- [ ] Unfolded asserts are ordered so a count is checked before the item it indexes
- [ ] More than three items sharing one fact are asserted once with `all()` or `any()`, the items interpolated
- [ ] Identity, enum members and `None` are compared with `is`
- [ ] Every `pytest.raises` matches an exception class, and the data the error carries is asserted after it
- [ ] No `match=` or `in` asserts a word of a message's prose — only a value the message promises to name

## References

- [tests-functions](tests-functions.md) - Related: Owns the `#: Then` block these assertions sit in, and the one behaviour they assert on
- [error-types](error-types.md) - Related: Owns the error types `pytest.raises` matches on, and the granularity that makes `match=` unnecessary
- [principle-least-surprise](principle-least-surprise.md) - Foundation: A failing test should say what it expected without being opened

## External References

- [pytest — Assertions about expected exceptions](https://docs.pytest.org/en/stable/how-to/assert.html#assertions-about-expected-exceptions)
