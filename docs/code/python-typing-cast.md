---
name: "python-typing-cast"
description: "When `typing.cast` is a last resort, the invariant every cast must state, and keeping one cast per invariant. Load when writing or reviewing a cast"
type: "core"
scope: "global"
---

# `typing.cast`

`typing.cast` asserts a type to the checker without checking the value at runtime. Use it only when the invariant is real and the checker cannot express it; [python-typing](python-typing.md) owns annotation honesty, while [python-typing-unreachable](python-typing-unreachable.md) owns paths the checker cannot prove dead.

## 1. Prefer Narrowing and Better Types

Treat a cast as a last resort. Prefer `isinstance`, `match`, `assert_never`, a better annotation, an overload, or a `TypeGuard`/`TypeIs` when one expresses the relationship. A cast is appropriate only when the relationship is true but the type checker cannot represent it.

```python
# ❌ Bad — the runtime check already narrows the value, so the cast hides the actual type flow
if isinstance(value, str):
    result = cast(str, value)
```

```python
# ✅ Good — the check narrows value without an unchecked assertion
if isinstance(value, str):
    result = value
```

## 2. State the Safety Invariant Beside Every Cast

Place a `# SAFETY: ...` comment directly before every `cast(...)`. It states why the value has the asserted type at that point and what invariant upholds that fact. “Cast to `T`” only restates the operation and is not a justification.

```python
# ❌ Bad — the comment names the requested type but gives no reason it is true
result = cast(str, value)
```

```python
# ✅ Good — the parser's successful string branch establishes the type
# SAFETY: this branch accepts only values decoded from a JSON string token
result = cast(str, value)
```

The comment is for a reviewer to check, not a claim that the cast validates the value. The invariant must be upheld by the surrounding code or an explicit contract.

## 3. Keep One Cast With Its Invariant

Keep a cast at the narrowest point that owns its invariant, preferably in a helper. Do not repeat the same assertion at call sites: duplicated casts separate the type claim from the code that establishes it and let the two drift.

```python
# ❌ Bad — each caller independently repeats the same unchecked claim
first = consume(cast(Token, parsed))
second = inspect(cast(Token, parsed))
```

```python
# ✅ Good — one helper owns the invariant and its cast
def token_from(parsed: object) -> Token:
    # SAFETY: parse_token returns only Token instances after validating the token tag
    return cast(Token, parsed)
```

## Checklist

Before committing code, verify:

- [ ] Each cast is still necessary after considering narrowing, a better annotation, an overload, or a type guard
- [ ] Every `cast(...)` is directly preceded by `# SAFETY:` explaining why the value has the asserted type and what upholds that invariant
- [ ] No safety comment merely restates the cast's target type
- [ ] Each invariant and its cast live in one place rather than being repeated at call sites

## References

- [python-typing](python-typing.md) - Extends: Owns annotation honesty and the type claims casts supplement
- [python-typing-unreachable](python-typing-unreachable.md) - Related: Owns safety comments for branches the checker cannot prove dead
