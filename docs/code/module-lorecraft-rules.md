---
name: "module-lorecraft-rules"
description: "The lorecraft.rules package's responsibility, role, boundary and invariants: how a rule is declared and identified, the rule groups and their rules, and a rule as a pure judgment of one input. Load when adding or moving code in lorecraft.rules, declaring, naming or documenting a rule, a removed rule, an engine condition or a group, or deciding whether code declares a rule or runs one"
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

- A value that identifies a rule: a release, a group's prefix and title, a code, a name, an alias code, a level,
  and the severity an engine condition fixes.
- A rule class, the base class an input kind gives it, and the places its occurrences may point at.
- A removed rule, the decorator that registers a declaration, and the registry, with every check it makes on a
  declaration as the package loads.
- An engine condition: what the engine reports about a subject before any rule runs, such as a file that does
  not decode. It is declared and rendered like a rule, under the engine's group `LC`, with a fixed severity in
  place of a level and no `check`.
- A rule group, as a subpackage: its `__ruleset__.py` declares the group as `GROUP_ID` and whatever else its rules
  share, its `__init__.py` holds only the docstring, and each of its rules is one module. The `LC` group is
  declared the same way, and the registry imports its `GROUP_ID` to hold the reservation.
- The input value types a rule reads: frozen values of Lorecraft's own types, holding facts, the subject's identity
  values a rule compares them with, such as a document's filename or a skill's directory name, and the
  specifications that govern them. An input the package governs, such as a skill's line count, holds no
  specification.

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
- The registry is built once, with `Registry.load`, where a command starts, and passed down to what reads it.
  Nothing below that composition root imports a registry instance or memoizes one.
- A code bound twice, a declaration left incomplete, a group, code or alias code written out of form, or a code
  in a group its kind may not use is a defect in this package. It is raised when the package loads, never reported
  as the user's fault.
- The `LC` group holds engine conditions alone, and every engine condition is in it.
- A release and a rule name are value objects a user's input will also build, so a malformed one raises an
  `Error` variant, whoever wrote it.

## Examples

```python
# ❌ Bad — the rule asks the database for the headings itself: it imports the layer above, which the import
# contract refuses, and a test of one heading rule now needs a whole revision
@rule
class EmptySection(HeadingsRule):
    @classmethod
    def check(cls, database: Database, ref: DocumentRef) -> tuple[Self, ...]:
        occurrences: list[Self] = []
        for headings_spec in database.headings_specs(ref):
            if headings_spec.forbid_empty_sections:
                for heading in database.parse(ref).headings:
                    if heading.empty:
                        occurrences.append(cls(spec=headings_spec.spec, line=heading.line, section=heading.text))
        return tuple(occurrences)
```

```python
# ✅ Good — the rule judges the input its base class fixes; the run built that input once from the queries
@rule
class EmptySection(HeadingsRule):
    @classmethod
    def check(cls, subject: HeadingsInput) -> tuple[Self, ...]:
        occurrences: list[Self] = []
        for headings_spec in subject.specs:
            if headings_spec.forbid_empty_sections:
                for heading in subject.headings:
                    if heading.empty:
                        occurrences.append(cls(spec=headings_spec.spec, line=heading.line, section=heading.text))
        return tuple(occurrences)
```

## Naming a Rule

A rule is named for what is wrong, as the established linters name theirs, so that its name reads as a setting:
`too-many-tokens = "warn"` says which way the rule fires, where `token-budget = "warn"` does not.

- **The name states the condition the rule reports**, never the limit, the subject or the fix. A limit exceeded is
  `too-many-<unit>`, and a required part absent is `missing-<part>`.
- **The class is the name in PascalCase and its module the name in snake case**, with no `Rule` or `Violation`
  suffix: `too-many-words` is `TooManyWords` in `too_many_words.py`.
- **A group's title is a plural noun phrase**, read as the heading of its rules in a list: `Length limits`.

## Writing the Diagnostic

- **`message()` states the condition in lowercase, without a trailing period**, with the value found against the
  limit in parentheses where there is one: `too many tokens (5200 > 4000)`. It names no path and no specification.
- **`children()` points a `Note` at the specification** that states the rule, at `Elsewhere(spec)`, so two
  occurrences from two specifications read apart. A rule every governed document is held to, with no key stating
  it, points its `Note` at the corpus's structure specification that governs the document. A rule the package
  itself states has `spec` `None`: its `Note` names the external specification that sets the limit in its text,
  with no `at`.
- **A `Help` gives the fix for this occurrence** when its fields make it concrete, such as how many tokens to cut.
  The general fix is the docstring's, but a rule the package states may add a `Help` with the fix the external
  specification itself prescribes.

## Documenting a Rule

The docstring is the rule's page in the rulebook, the one a user opens when a diagnostic prints its code. Write
it as Ruff and Clippy write theirs, for a user who knows their documents, skills and specifications, and nothing
of this package.

- **The summary line states the condition**, about the user's subject.
- **What it does** opens with "Checks for" and the subjects the rule reports, then names the specification key
  that sets the limit or states the rule; a rule every governed document is held to says that no key states it,
  and a rule the package states names the external specification and its figure instead. It adds each case a user would not guess: what counts, what does not, how several
  specifications combine.
- **Why is this bad?** is one or two sentences on what the condition costs the agent that loads the subject, never
  only that a specification forbids it.
- **Example** is the input that breaks the rule, under invented paths, in fenced blocks in each file's language:
  the specification excerpt, then the subject. For a rule every governed document is held to, the excerpt is of a
  governing specification that states some other rule; for a rule the package states, the subject alone. A subject whose
  length is the point is cut short with a comment, such as `<!-- ... 1800 more tokens -->`.
- **Use instead** is the same subject fixed, in a fenced block, after at most one sentence naming the change. It
  never shows raising the limit.
- *Known problems* follows only when the rule misfires on a case a user meets, and *Deviations from upstream* only
  on a rule with alias codes.
- **Nothing of the implementation.** No section names a tokenizer, a parser, a query, an input, a class or a
  field: a user acts only on what they can see or configure. The fields are documented in the `Attributes:` block
  after the sections, for the maintainer.

```python
# ❌ Bad — the page describes the machinery: a user over the cap learns which parser counts and which input the
# rule reads, but not whether a code block counts, and `word-cap = "warn"` does not say which way the rule fires
class WordCap(HeadingsRule):
    """Compares each section's word count from the Markdown parser with its outline entry's cap.

    ## What it does

    Splits each `SectionWords.text` on whitespace and reports `WordCap` when the count exceeds `cap`.
    """
```

```python
# ✅ Good — the name states what is wrong, and the page speaks of the user's section and specification
class TooManyWords(HeadingsRule):
    """A section is longer than its word cap allows.

    ## What it does

    Checks for sections longer than the `words` cap their outline entry sets in the structure specification.
    Subsections count toward it; fenced code blocks and table rows do not.
    """
```

## Checklist

Before committing code, verify:

- [ ] Nothing added to `lorecraft.rules` reads the disk, a view, a query or a configuration
- [ ] A new rule's `check` takes the one input its base class fixes and returns occurrences that name no subject
- [ ] A new rule is declared with `@rule` in its own module, in its group's subpackage, and listed nowhere else
- [ ] Decoding, building an input, running the rules, applying a level and rendering stay out of the package
- [ ] A new rule's name states the condition it reports, and its class and module spell that name
- [ ] A new rule's `message()` is lowercase with the value found against the limit, and `children()` points a
      `Note` at the specification that states the rule, at the corpus's structure specification when no key states
      it, or, when the package states it, names the external specification in the `Note`'s text with no `at`
- [ ] A new rule's docstring opens *What it does* with "Checks for", shows the broken and the fixed input under
      *Example* and *Use instead*, and names nothing of the implementation; a rule no key states says so, and its
      *Example* shows a governing specification's excerpt, then the subject; a rule the package states names the
      external specification and its figure, and its *Example* shows the subject alone

## References

- [adr-001-snapshot-model](../arch/adr-001-snapshot-model.md) - Foundation: The Analysis role
- [adr-009-rules](../arch/adr-009-rules.md) - Foundation: A rule's declaration, its docstring's sections and the
  rulebook
- [adr-010-diagnostics](../arch/adr-010-diagnostics.md) - Foundation: The message, help and notes of a diagnostic
- [principle-single-responsibility](principle-single-responsibility.md) - Foundation: One reason to change
- [pattern-registry](pattern-registry.md) - Foundation: The one list a package walk builds
- [python-docstrings](python-docstrings.md) - Foundation: The summary line and the `Attributes:` block of a rule's
  docstring

## External References

- [Ruff — Proposing lint rules](https://docs.astral.sh/ruff/rule-proposals/)
- [Clippy — Adding a new lint: Documentation](https://doc.rust-lang.org/nightly/clippy/development/adding_lints.html#documentation)
- [RFC 344 — Lints](https://rust-lang.github.io/rfcs/0344-conventions-galore.html#lints)
