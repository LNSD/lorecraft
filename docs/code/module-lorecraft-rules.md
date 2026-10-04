---
name: "module-lorecraft-rules"
description: "The lorecraft.rules package's responsibility, role, boundary and invariants: how a rule is declared and identified, the rule groups and their rules, and a rule as a pure judgment of one input. Load when adding or moving code in lorecraft.rules, declaring a rule, a removed rule or a group, or deciding whether code declares a rule or runs one"
type: "pkg"
scope: "pkg:lorecraft.rules"
---

# The `lorecraft.rules` Package

## Responsibility

Declare the rules a subject is judged by. It changes when a rule is added, changed or removed, or when what a
declaration states changes: a rule's identity, the places its occurrences point at, or the input it reads.

## Role

**Analysis**, the judging half of it. A rule is a pure judgment of one input value, and this package holds the
rules with everything that makes one a rule: its identity, the class that declares and checks it, and the
registry that lists them all. The database that builds the inputs and the run that hands them over sit above it,
in `lorecraft.checks`, so a rule has nothing to read but the input it is handed.

## Belongs Here

- A value that identifies a rule: a release, a group's prefix and title, a code, a name, an alias code, a level.
- A rule class, the base class an input kind gives it, and the places its occurrences may point at.
- A removed rule, the decorator that registers a declaration, and the registry, with every check it makes on a
  declaration as the package loads.
- A rule group, as a subpackage stating its prefix and title, and each of its rules, one module per rule.
- The input value types a rule reads: frozen values of Lorecraft's own types, holding facts and the
  specifications that govern them.

## Belongs Elsewhere

| Code that… | Belongs in |
|---|---|
| Answers or memoizes a query over one revision, decoding a subject included | `lorecraft.checks` |
| Builds a rule's input from the queries, or runs the rules over a subject | `lorecraft.checks` |
| Applies a level, files an occurrence under its subject, or holds a report | `lorecraft.checks` |
| Prints, renders a report, or sets an exit code | `lorecraft.cli` |
| Parses text, or decodes a specification | `lorecraft.project` |
| Reads the disk | `lorecraft.vfs` |

## Invariants

- A rule never imports `lorecraft.checks`. The layers contract puts this package below it, so the database, a
  query and the run are out of a rule's reach by import, not by review.
- A rule reads the one input its class fixes and nothing else, and performs no I/O.
- An occurrence names no subject. It points at a line of the subject or at the subject itself, and the run that
  checked the subject supplies the path.
- The registry is package data: it reads no workspace and is not a query, and it holds this package's rules,
  never a rule its unit tests declare.
- A code bound twice, a declaration left incomplete, or a group, code or alias code written out of form is a
  defect in this package. It is raised when the package loads, never reported as the user's fault.
- A release and a rule name are value objects a user's input will also build, so a malformed one raises an
  `Error` variant, whoever wrote it.

## Examples

```python
# ❌ Bad — the rule asks the database for the headings itself: it imports the layer above, which the import
# contract refuses, and a test of one heading rule now needs a whole revision
@rule
class EmptySection(OutlineRule):
    @classmethod
    def check(cls, database: Database, ref: DocumentRef) -> tuple[Self, ...]:
        return tuple(cls(line=h.line) for h in database.parse(ref).headings if not h.body)
```

```python
# ✅ Good — the rule judges the input its base class fixes; the run built that input once from the queries
@rule
class EmptySection(OutlineRule):
    @classmethod
    def check(cls, subject: OutlineInput) -> tuple[Self, ...]:
        return tuple(cls(line=h.line) for h in subject.headings if not h.body)
```

## Checklist

Before committing code, verify:

- [ ] Nothing added to `lorecraft.rules` reads the disk, a view, a query or a configuration
- [ ] A new rule's `check` takes the one input its base class fixes and returns occurrences that name no subject
- [ ] A new rule is declared with `@rule` in its own module, in its group's subpackage, and listed nowhere else
- [ ] Decoding, building an input, running the rules, applying a level and rendering stay out of the package

## References

- [adr-001-snapshot-model](../arch/adr-001-snapshot-model.md) - Foundation: The Analysis role
- [principle-single-responsibility](principle-single-responsibility.md) - Foundation: One reason to change
- [pattern-registry](pattern-registry.md) - Foundation: The one list a package walk builds
