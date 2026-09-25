---
name: "pattern-state"
description: "State-specific objects own behavior and transitions when several operations depend on one lifecycle state. Load when methods repeat branches over the same state flag or a transition must change which operations are valid"
type: "core"
scope: "global"
---

# State (Behavior by Lifecycle State)

## Rule

Use state objects when several operations change behavior according to the same lifecycle state and
transition rules are growing hard to keep consistent. Each state implements the operations that make sense
there and returns or installs the next state when a transition occurs. The owner delegates state-dependent
work to its current state rather than repeating a branch over a string flag in every method.

Keep the set of states and the legal transitions visible. Represent impossible transitions explicitly: raise
a domain error or return a documented unchanged state, according to the operation's contract. Put data that
belongs to the whole entity on the owner; state objects should carry only state-specific data or behavior.

## Examples

A document has two operations that change together when it is published:

```python
# ❌ Bad — every new operation adds another branch over the same string state.
class Document:
    def __init__(self) -> None:
        self.state = 'draft'

    def publish(self) -> None:
        if self.state == 'draft':
            self.state = 'published'

    def label(self) -> str:
        if self.state == 'draft':
            return 'Draft'
        return 'Published'
```

```python
# ✅ Good — each state owns its behavior and transition; the owner delegates.
from __future__ import annotations


class Draft:
    def publish(self) -> Published:
        return Published()

    def label(self) -> str:
        return 'Draft'


class Published:
    def publish(self) -> Published:
        return self

    def label(self) -> str:
        return 'Published'


type ReviewState = Draft | Published


class Document:
    def __init__(self) -> None:
        self._state: ReviewState = Draft()

    def publish(self) -> None:
        self._state = self._state.publish()

    def label(self) -> str:
        return self._state.label()
```

## Why It Matters

Branches scattered across methods can disagree about which states exist or what a transition means. State
objects keep the behavior for one lifecycle phase together. Adding a new state then makes the operations it
must support visible, while the owner retains one clear delegation path.

## Pragmatism Caveat

For a small, fixed lifecycle with one state-dependent operation, an enum and a branch are easier to read.
Do not create a class for every boolean flag. This pattern also does not replace resource cleanup:
acquisition and release still follow the resource lifecycle rule, regardless of how states are represented.
When a transition establishes a prerequisite for later operations, use distinct types to make that order
visible to a static checker instead.

## Checklist

- [ ] Several operations depend on the same lifecycle state
- [ ] Each state owns its behavior and defines legal transitions
- [ ] The owner delegates instead of repeating branches on a state flag
- [ ] Impossible transitions have one documented outcome
- [ ] Shared entity data remains on the owner rather than being copied between states

## References

- [principle-single-responsibility](principle-single-responsibility.md) - Foundation: Keep one state's behavior together
- [pattern-resource-lifecycle](pattern-resource-lifecycle.md) - Related: Resource cleanup remains exception-safe across transitions
- [pattern-typestate](pattern-typestate.md) - Related: Distinct types expose valid operations after a transition

## External References

- [Refactoring.Guru — State](https://refactoring.guru/design-patterns/state)
