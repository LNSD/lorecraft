---
name: "python-fn-unchecked"
description: "Unchecked constructors that skip a value object's validation, with a Safety docstring and a SAFETY comment at each call site. Load when adding or reviewing an unchecked constructor"
type: "core"
scope: "global"
---

# Unchecked Constructors

An unchecked constructor transfers the proof of a value object's invariant to its caller. **The bypass must be
visible both where the method is declared and where it is called.** The invariant itself belongs in the value
type's documentation; this document owns how a bypass records the obligation. The runtime invariant is owned by
[pattern-value-object](pattern-value-object.md).

## 1. Use Unchecked Construction Only With an Existing Proof

Use an unchecked constructor only when the call site already has a concrete reason to know the value satisfies
the invariant, such as a fixed literal or a value read from a store that validated it on write. Values arriving
from CLI arguments, configuration, files, or other external boundaries go through the validating constructor.
Skipping validation without an independent proof moves the failure away from the boundary and makes malformed
values harder to trace.

## 2. Name the Bypass and Reference the Type's Invariant

Include `_unchecked` in the method name and document that it skips validation. Its docstring's `# Safety` section
points to the invariant documented on the value type instead of restating that invariant, so the type's
documentation remains its single source of truth.

```python
@dataclass(frozen=True, slots=True)
class TenantName:
    """A tenant name containing a non-empty lowercase identifier."""

    value: str

    @classmethod
    def from_str_unchecked(cls, raw: str) -> 'TenantName':
        """Wrap a tenant name without validating it.

        # Safety
        The caller must ensure ``raw`` satisfies the invariant documented by ``TenantName``. This method performs
        no validation.
        """
        instance = object.__new__(cls)
        object.__setattr__(instance, 'value', raw)
        return instance
```

## 3. Mark Every Call Site With Its Proof

Put a `# SAFETY:` comment immediately above each unchecked call outside tests. State why the value already
satisfies the type's invariant; a bare assertion that it is valid gives a reviewer nothing to check. Tests may
omit the comment when the value is visible as a literal in the same expression.

```python
# ✅ Good — the constant is a fixed, reviewed value and the comment exposes why the bypass holds.
# SAFETY: This fixed literal satisfies the TenantName invariant.
DEFAULT_TENANT: TenantName = TenantName.from_str_unchecked('system')
```

## 4. Keep the Bypass Narrow

Keep an unchecked constructor private to the package or module when its callers permit it, and use it only at
sites that hold the proof. Do not use it to avoid validation for convenience or speed; ordinary inputs must
continue through the validating constructor.

## Checklist

Before committing code, verify:

- [ ] Every unchecked constructor name contains `_unchecked` and its docstring says it skips validation
- [ ] The constructor's `# Safety` section refers to the invariant in the value type's documentation without
      restating the invariant
- [ ] Every non-test call has an immediately preceding `# SAFETY:` comment that explains its proof
- [ ] External input still goes through the validating constructor
- [ ] The unchecked constructor is no more visible than its callers require

## References

- [pattern-value-object](pattern-value-object.md) - Related: Owns the runtime invariant on a wrapped primitive
- [python-docstrings](python-docstrings.md) - Related: Owns docstring structure and required sections

