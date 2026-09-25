---
name: "pattern-registry"
description: "Name-keyed registration lets commands join a shared router beside their handlers. Load when a new command would require editing a central dispatcher or import list, or when adding command discovery"
type: "core"
scope: "global"
---

# Registry (Name-Keyed Extension Seam)

## Rule

When independently defined handlers join an open set of commands, register each handler under its public name beside its definition. Discover the handler modules once before mounting commands. The router reads the registered names in a stable order and does not contain a branch or import for each command.

Reject a name already bound to a different handler. Import failures for built-in commands must propagate: silently skipping a module would publish an incomplete command surface. Keep registration separate from execution; a registration decorator returns the original callable unchanged.

## Examples

A command family grows without changing the router:

```python
# ❌ Bad — every command adds another branch to the central router.
def run_command(name: str) -> None:
    if name == 'check':
        check()
    elif name == 'version':
        version()
    else:
        raise ValueError(f'unknown command: {name}')
```

```python
# ✅ Good — each handler registers its name where it is defined.
from collections.abc import Callable

Handler = Callable[[], None]
handlers: dict[str, Handler] = {}


def register(name: str, handler: Handler) -> None:
    if name in handlers and handlers[name] is not handler:
        raise ValueError(f'duplicate command: {name}')
    handlers[name] = handler


def run_command(name: str) -> None:
    handlers[name]()


register('check', check)
register('version', version)
```

## Why It Matters

A central branch or import list makes every new command edit the same file. Registration keeps the new name beside its handler, while duplicate detection prevents one handler from silently replacing another. One-time discovery makes registration available before dispatch and avoids repeated import work.

## Pragmatism Caveat

Use a direct call or a small fixed mapping for a closed set of choices. Package discovery is useful when commands live in separate modules and can grow independently. It adds indirection, so keep the registration path simple and let failures from built-in modules surface immediately.

## Checklist

- [ ] An independently added command registers its name beside its handler
- [ ] The router discovers handlers before mounting them, without an import or branch per command
- [ ] Discovery runs once and import failures for built-in commands propagate
- [ ] Registering a different handler under an occupied name raises an error
- [ ] A registration decorator preserves the original callable
- [ ] Commands mount in a stable order

## References

- [principle-information-hiding](principle-information-hiding.md) - Foundation: The router exposes commands without exposing its registration storage
- [pattern-decorator](pattern-decorator.md) - Related: A registration decorator records a callable without wrapping its behavior

## External References

- [Python docs — `pkgutil.iter_modules`](https://docs.python.org/3/library/pkgutil.html#pkgutil.iter_modules)
