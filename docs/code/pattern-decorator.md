---
name: "pattern-decorator"
description: "Wrap a callable to add one reusable behavior while preserving its call contract and metadata. Load when adding the same tracing, timing, or access check around several functions, or when writing a decorator that replaces a function"
type: "core"
scope: "global"
---

# Decorator (Reusable Callable Behavior)

## Rule

Use a decorator when the same behavior surrounds several callables and belongs neither in their core work
nor in each caller. Keep the wrapper's added responsibility narrow. Call the wrapped function exactly once
on the normal path, pass its arguments through, return its value, and let its exception propagate unless
changing that contract is the decorator's stated purpose.

For a function wrapper, use `functools.wraps` so introspection retains the wrapped function's name,
documentation, and `__wrapped__` link. On Python 3.12+, use `ParamSpec`-style type parameters to preserve
the callable's parameter and return types. A registration decorator that returns its input unchanged has a
different purpose: it belongs to the registry pattern, not this rule.

## Examples

Add a trace line around several checks without erasing their callable contract:

```python
# ❌ Bad — the wrapper loses the original signature and metadata.
import logging
from collections.abc import Callable

logger: logging.Logger = logging.getLogger(__name__)


def traced(function: Callable[..., object]) -> Callable[..., object]:
    def wrapper(*args: object, **kwargs: object) -> object:
        logger.debug('Started %s', function.__name__)
        return function(*args, **kwargs)

    return wrapper
```

```python
# ✅ Good — the wrapper preserves types and metadata, then returns the original result.
import logging
from collections.abc import Callable
from functools import wraps

logger: logging.Logger = logging.getLogger(__name__)


def traced[**P, R](function: Callable[P, R]) -> Callable[P, R]:
    @wraps(function)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        logger.debug('Started %s', function.__name__)
        return function(*args, **kwargs)

    return wrapper
```

## Why It Matters

Copying the same wrapper logic into each function gives it several places to drift. An untyped decorator
also hides call errors from a type checker, and a wrapper without `wraps` presents its own name and docstring
to tools that inspect the callable. Preserving the contract makes the added behavior easier to adopt and
remove without changing callers.

## Pragmatism Caveat

For one function, an ordinary call or `try` block is usually clearer. Do not wrap a function to hide a
substantial workflow, to swallow errors, or to change arguments unexpectedly. If callers must choose when
the extra behavior runs, make that choice explicit at the call site.

## Checklist

- [ ] Several callables need the same narrow behavior around their core work
- [ ] The wrapper forwards arguments and returns the wrapped result without changing the contract unexpectedly
- [ ] The wrapper uses `functools.wraps` and preserves parameter and return types
- [ ] Exceptions propagate unless translation is part of the decorator's documented contract
- [ ] Registration-only decorators follow the registry rule instead

## References

- [principle-least-surprise](principle-least-surprise.md) - Foundation: Preserve the callable behavior its signature promises
- [pattern-registry](pattern-registry.md) - Related: Registration decorators record a callable without wrapping its behavior
- [python-typing](python-typing.md) - Related: Keep public callable annotations honest

## External References

- [Python docs — `functools.wraps`](https://docs.python.org/3.12/library/functools.html#functools.wraps)
- [Real Python — Primer on Python Decorators](https://realpython.com/primer-on-python-decorators/)
