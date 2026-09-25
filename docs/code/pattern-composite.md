---
name: "pattern-composite"
description: "Leaves and groups support the same operation so callers can process a recursive tree without branching on node kind. Load when documents, rules, or results form nested groups and callers repeat leaf-versus-container checks"
type: "core"
scope: "global"
---

# Composite (One Operation Across a Tree)

## Rule

Use a composite when the domain is a tree and callers need the same operation on one leaf or a group of
leaves. Give both a small common contract. A group implements the operation by asking its children to do
their part; callers invoke the operation without inspecting every node's concrete type.

Keep tree ownership and traversal clear. A composite should contain children and combine their results,
while a leaf performs its own work. In Python, a `Protocol` or straightforward duck typing can express the
shared operation without forcing every node into an inheritance hierarchy. Specify whether traversal order
matters and whether the group may be empty.

## Examples

A rule group and a single rule both produce findings for a document:

```python
# ❌ Bad — each caller must know which node kind it received and recurse itself.
def findings(node: Rule | RuleGroup, text: str) -> list[str]:
    if isinstance(node, RuleGroup):
        return [finding for child in node.children for finding in findings(child, text)]
    return node.check(text)
```

```python
# ✅ Good — leaves and groups share check(); recursion stays inside the group.
from typing import Protocol


class Check(Protocol):
    def check(self, text: str) -> list[str]: ...


class RequiredTitle:
    def check(self, text: str) -> list[str]:
        return [] if text.startswith('# ') else ['missing title']


class CheckGroup:
    def __init__(self, children: tuple[Check, ...]) -> None:
        self._children = children

    def check(self, text: str) -> list[str]:
        found: list[str] = []
        for child in self._children:
            found.extend(child.check(text))
        return found
```

## Why It Matters

When traversal is repeated at call sites, each caller can omit a nested child, use a different order, or
special-case a node type differently. A shared operation makes the tree's behavior local to its nodes and
lets a caller treat one rule and a group of rules uniformly.

## Pragmatism Caveat

Do not build a composite for a flat list whose items are already processed by one simple loop. If leaves
and groups do not share a meaningful operation, a common interface hides a real difference. For a small
fixed tree with one traversal, a plain recursive function can be clearer.

## Checklist

- [ ] The domain is genuinely recursive, with leaves and groups that share an operation
- [ ] Callers invoke the common operation without branching on node kind
- [ ] Groups delegate to children and combine results without taking over leaf work
- [ ] Child order and empty-group behavior are explicit
- [ ] A flat collection or one recursive function would not be simpler

## References

- [principle-single-responsibility](principle-single-responsibility.md) - Foundation: Leaves and groups each own their part of the operation
- [pattern-facade](pattern-facade.md) - Related: A facade coordinates a workflow, while a composite represents a recursive structure

## External References

- [Python Design Patterns — Composite](https://python-patterns.guide/gang-of-four/composite/)
- [Refactoring.Guru — Composite](https://refactoring.guru/design-patterns/composite)
