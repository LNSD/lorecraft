---
name: "code-python-typing"
description: "Responsibility of the `docs/code/python-typing*.md` code rules: standard Python typing practices and idioms, and what belongs in a neighbouring group instead. Load when creating or editing a python-typing document in docs/code/, or deciding whether a typing rule belongs there"
type: "meta"
scope: "global"
---

# Python Typing Code Rule Responsibility

**The `python-typing-*` group has one responsibility: the standard Python typing practices and idioms this
project writes.** A document belongs in the group when its subject is what the code tells the type system, or
what `ty` proves from it.

This spec narrows [code-python](code-python.md). It adds no template: a `python-typing-*` document keeps the
python structure, its doctrine paragraph, numbered rule sections, Checklist and References. What it adds is the
boundary of the group, so a typing rule has one home and a rule about something else does not settle there
because it mentions a type.

## Responsibility

The group owns how Python's own type system is used: how an annotation is spelled and when it is written, which
construct of `typing`, `collections.abc` or the builtin generics expresses a claim, the qualifiers that change
what a checker allows, and the idioms that let `ty` prove a property instead of a runtime guard checking it.

`python-typing` is the parent. It owns the rules every member relies on: annotation spelling, annotation honesty,
and making an invalid state unrepresentable. Each `python-typing-<construct>` member owns one typing construct
or idiom, and names the parent `Extends` as [code-python](code-python.md) requires.

## Belongs Here

A rule belongs in the group when all of these hold:

- **Its subject is a typing construct or idiom**: an annotation form, a `typing` or `collections.abc` construct,
  a qualifier, or a way of shaping types the checker reads.
- **It is standard Python.** The construct comes from the language or its standard library, and the rule would
  hold in any project that checks its types the way this one does.
- **What it enforces is a static claim.** The checker either proves the rule or, where it cannot, the rule says
  what fails loudly at runtime in its place.

## Belongs Elsewhere

A rule that only mentions a type is owned by the group its subject names:

| When the rule is about | It belongs in |
|---|---|
| Whether to introduce an abstraction at all: a shared contract, a validated value, a wrapper | the `pattern-*` document for that design, which the typing member points to |
| How a record is declared, defaulted or validated at runtime | `python-dataclasses` |
| What a typed thing is called | `python-naming` |
| The types and API of one third-party package | the `python-*` document scoped to that package |
| How a failure is declared, raised or handled | the `error-*` group |

A typing member and its design neighbour split one subject in two: the `pattern-*` document owns when to use
the design, and the typing member owns how the construct is spelled and what `ty` proves about it. Each names
the other with an ownership pointer and states neither rule twice.

## Frontmatter

`scope` is always `"global"`. The group's constructs come from the language and its standard library, which
have no package to name, so the `pkg:pypi/<name>` scope that [code-python](code-python.md) allows is not open
here. A rule that needs a package's own types belongs to that package's document.

## Checklist

Before committing a `python-typing-*` document, verify:

- [ ] Its subject is one typing construct or idiom, and the parent `python-typing` owns the cross-cutting rules
- [ ] Every rule is about what the type system is told or what `ty` proves, not runtime behaviour
- [ ] Every construct it governs is standard Python, not a third-party package's type
- [ ] A design decision about when to introduce an abstraction is pointed to in its `pattern-*` document, not
      restated
- [ ] `scope` is `"global"`

## References

- [code-python](code-python.md) - Extends: Python convention template that this spec narrows
