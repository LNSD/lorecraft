---
name: "python-fn"
description: "Function parameter shape and defaults: keyword-only arguments, immutable defaults, and explicit absence. Load when defining a function with optional parameters or changing how callers pass arguments"
type: "core"
scope: "global"
---

# Function Parameters and Defaults

A function signature tells callers which values are essential, which options need names, and what omission
means. Choose parameter kinds and defaults so that a call explains itself and one call cannot change another
call's starting state. Type spelling is owned by [python-typing](python-typing.md). Parameter prose is owned
by [python-docstrings](python-docstrings.md).

## 1. Make Ambiguous Options Keyword-Only

Put `*` before optional parameters whose meaning is unclear at a positional call site. A call such as
`load_schema(corpus, aspect, kind)` asks the reader to recall an argument order; named options show which
selection was made. Keep an argument positional when its role is already clear and positional use is natural.

```python
# ❌ Bad — the third argument's meaning is invisible at the call site
def load_schema(corpus: str, aspect: str | None = None, kind: str | None = None) -> str:
    ...


schema = load_schema('code', None, 'structure')
```

```python
# ✅ Good — the option names travel with the call
def load_schema(corpus: str, aspect: str | None = None, *, kind: str | None = None) -> str:
    ...


schema = load_schema('code', kind='structure')
```

## 2. Use Immutable Defaults and Create Mutable Values Per Call

A default expression is evaluated when the function is defined, not at every call. Use immutable values
directly. When omission means a fresh list, dict, or set, default to `None` and construct the value inside the
function. A mutable default can carry one call's changes into the next.

```python
# ❌ Bad — findings from an earlier call remain in the shared list
def collect_findings(document: str, findings: list[str] = []) -> list[str]:
    findings.append(document)
    return findings
```

```python
# ✅ Good — an omitted collection starts fresh on every call
def collect_findings(document: str, findings: list[str] | None = None) -> list[str]:
    if findings is None:
        findings = []
    findings.append(document)
    return findings
```

## 3. Test Absence With `is None`

Use `is None` when `None` means an argument was omitted. Truthiness also treats `''`, `0`, `False`, and empty
containers as absent, even when a caller deliberately supplied them. This matters whenever a default selects
a fallback rather than merely testing whether a value is nonempty.

```python
# ❌ Bad — an explicit empty prefix is replaced by the default
def report_prefix(prefix: str | None = None) -> str:
    return prefix or 'check'
```

```python
# ✅ Good — only omission selects the default
def report_prefix(prefix: str | None = None) -> str:
    if prefix is None:
        return 'check'
    return prefix
```

## Checklist

Before committing code, verify:

- [ ] Optional arguments whose positional meaning is unclear follow `*`, and call sites name them
- [ ] Defaults are immutable; an omitted mutable value is created inside the function
- [ ] A fallback for an omitted argument tests `is None`, preserving explicitly supplied false values

## References

- [python-typing](python-typing.md) - Related: Owns the annotation on each parameter and return value
- [python-docstrings](python-docstrings.md) - Related: Owns prose for parameters whose names need explanation
- [python-dataclasses](python-dataclasses.md) - Related: Owns defaults for fields on structured records

## External References

- [Python tutorial: Defining Functions](https://docs.python.org/3.12/tutorial/controlflow.html#more-on-defining-functions)
- [Google Python Style Guide: Default Argument Values](https://google.github.io/styleguide/pyguide.html#212-default-argument-values)
- [Real Python: Mutable Default Arguments](https://realpython.com/python-or-operator/#mutable-default-arguments)
