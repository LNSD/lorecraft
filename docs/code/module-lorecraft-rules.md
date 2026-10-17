---
name: "module-lorecraft-rules"
description: "The lorecraft.rules package's responsibility, role, boundary and invariants: how a rule is declared and identified, the rule groups and their rules, a rule as a pure judgment of one subject, and the selection, table and report of a run. Load when adding or moving code in lorecraft.rules, declaring, naming or documenting a rule or a group, changing a run's selection, table or report, or deciding whether code declares a rule or runs one"
type: "pkg"
scope: "pkg:lorecraft.rules"
---

# The `lorecraft.rules` Package

## Responsibility

Declare the rules a subject is judged by, and how a run enables and reports them. It changes when a
rule is added, changed or removed, or when what a declaration states changes: a rule's identity, the places
its occurrences point at, or the query it names. It also changes with a run's selection, table or report.

## Role

**Analysis**, the judging half of it. A rule is a pure judgment of one subject's query facts, and this
package holds the rules with everything that makes one a rule: its identity and class,
and the registry that lists them all, with the values a run is stated in. The run that resolves a rule's
query and hands it the facts sits above in `lorecraft.engine`; the query is answered by the database in
`lorecraft.project`, so a rule reads only its facts.

## Belongs Here

- A value that identifies a rule: a release, a group's prefix and title, a code, a name, an alias code, a level, and
  the severity an engine condition fixes.
- A rule class, the base class its subject kind gives it, and the places its occurrences may point at. A subject
  kind's base has a `Queried` form that names the query the rule needs and judges its facts; a document's also
  requires the rule to declare the facet it reads, from the facets this package states. A rule over what any
  Markdown file has judges a document, a `SKILL.md` and a resource alike; a rule over one of a skill's files judges a `SKILL.md` and a resource, never a document. A base over an item binds the kinds it applies to; `governing_facet` states the facet a rule reads, and a base
  over what a document and a skill share, such as the frontmatter, declares the facet a document is gated on.
- A removed rule, the decorator that registers a declaration and the registry.
- The rule index, `lorecraft.rules.index`: identity as plain tuples and strings, with the lookups the command
  line's edge needs, importing only `typing`; generated from the registry, never a source of rules.
- An engine condition: what the engine reports before any rule runs, such as an undecodable file.
  Declared and rendered like a rule, with an `EngineCode` in group `LC`, a fixed severity, no `judge`; it
  derives from `FileCondition` or `EntryCondition`.
- The one-run selection, the rule table and the report of a run, each stated in its module docstring.
- A rule group, as a subpackage: its `__ruleset__.py` declares the group as `GROUP_ID` and whatever else its rules
  share, its `__init__.py` holds only the docstring, each rule is one module. The `LC` group is declared in
  `identity.py` as `ENGINE_GROUP`, for `EngineCode`, and re-exported as its `GROUP_ID`.
- A rule's query, per ADR-026: in its module, in the group's `__ruleset__.py` when its rules share it, in
  `lorecraft.project` when several groups do. A `judge` names its parameter `facts`.

## Belongs Elsewhere

| Code that… | Belongs in |
|---|---|
| Answers or memoizes a query over one revision, decoding a subject included | `lorecraft.project` |
| Runs the rules over a subject, and files each occurrence as a diagnostic | `lorecraft.engine` |
| Prints, renders a report, or sets an exit code | `lorecraft.cli` |
| Parses text, or decodes a meta spec | `lorecraft.project` |
| Reads the disk | `lorecraft.vfs` |

## Invariants

- Nothing here imports `lorecraft.engine` or `lorecraft.project.database`. The layers contract puts this package
  below the first and a forbidden contract refuses the second, so the database, a query and the run are out of
  reach by import.
- A rule reads only the facts of the query it names, and performs no I/O.
- An occurrence names no subject: it points at a line of the subject or at the subject itself, and the run
  supplies the path.
- The registry is package data: it reads no workspace, is not a query, and holds this package's rules, never a
  test's.
- The registry is built once, with `Registry.load`, where a command starts, and passed down; nothing below imports
  an instance or memoizes one.
- A code bound twice, a declaration left incomplete, a group with no title, a code numbered out of range, or a
  code in a group its kind may not use is a defect in this package, raised when it loads, never the user's fault.
- The `LC` group holds engine conditions alone, each coded with an `EngineCode`, which names no other group.
- A release, a rule name, a group's prefix, an alias code's linter and upstream code, and a code prefix are
  value objects a user's input will also build, so a malformed one raises an `Error`, whoever wrote it.

## Examples

```python
# ❌ Bad — the rule asks the database for the headings itself: it imports the database, which the import
# contracts refuse, and a test of one heading rule now needs a whole revision
@rule
class EmptySection(DocumentRule):
    @classmethod
    def check(cls, database: Database, source: DocumentText) -> tuple[Self, ...]:
        occurrences: list[Self] = []
        for structure_spec in database.model().find_governance(source.ref).structure_specs():
            if structure_spec.forbid_empty_sections:
                for heading in database.parse(source).headings:
                    if heading.empty:
                        occurrences.append(cls(spec=structure_spec.path, line=heading.line, section=heading.text))
        return tuple(occurrences)
```

```python
# ✅ Good — the rule names its query and judges the facts it returns; the query is memoized by the database
@rule
class EmptySection(QueriedDocumentRule[EmptySectionFacts]):
    @classmethod
    def query(cls) -> Query[EmptySectionFacts]:
        return empty_section_facts

    @classmethod
    def judge(cls, facts: EmptySectionFacts, /) -> tuple[Self, ...]:
        return tuple(
            cls(spec=spec, line=heading.line, section=heading.text)
            for spec in facts.forbidding_specs
            for heading in facts.empty_headings
        )
```

## Naming a Rule

A rule is named for what is wrong, as the established linters name theirs, so its name reads as a setting:
`too-many-tokens = "warn"` says which way the rule fires, where `token-budget = "warn"` does not.

- **The name states the condition the rule reports**, never the limit, the subject or the fix. A limit on a count
  is `too-many-<unit>`, or `<part>-too-many-<unit>` for one part; on a length in characters, `<part>-too-long`, as
  linters name `line-too-long`; a required part absent is `missing-<part>`.
- **The class is the name in PascalCase and its module the name in snake case**, with no `Rule` or `Violation`
  suffix: `section-too-many-words` is `SectionTooManyWords` in `section_too_many_words.py`.
- **A group's title is a plural noun phrase**, read as the heading of its rules in a list: `Length limits`.

## Writing the Diagnostic

- **`message()` states the condition in lowercase, without a trailing period**, with the value found against the
  limit in parentheses where there is one: `too many tokens (5200 > 4000)`. It names no path and no meta spec, and
  never branches on a plural.
- **`children()` points a `Note` at the meta spec** that states the rule, at `Elsewhere(spec)`, so two
  occurrences from two meta specs read apart. A rule every governed document is held to, with no key stating
  it, points its `Note` at the corpus's structure file that governs the document, unless no schema in
  that file states the rule either, as for a document's `name` held to its filename: that rule carries no
  `Note` pointing at a schema, and says in its own words what it requires. A title rule, held to by every governed
  document, has `spec` `None` and carries no meta spec `Note`. A rule the package
  itself states has `spec` `None`: its `Note` names the external specification that sets the limit in its text,
  with no `at`. A rule over an Agent Skills field names the Agent Skills specification in a
  group-level `Note`, written once in the group's `__ruleset__.py` and placed first in `children()`. A rule the
  package states that no external specification sets carries no meta spec `Note`.
- **A `Help` gives the fix for this occurrence** when its fields make it concrete, such as the description an
  outline gives a section the document lacks. A limit's message already names the value found against it, so a
  `Help` restating the difference adds nothing; a `Label` places the overrun at a line, and may state the amount
  past the limit. The general fix is the docstring's, but a rule may give it as a
  fixed `Help`, such as "move the title above every section", and a rule the package states may add a `Help`
  with the fix the external specification itself prescribes. `children()` orders the meta spec `Note` first,
  then the `Help`, then the other `Note`s.

## Documenting a Rule

The docstring is the rule's rulebook page, which a user opens when a diagnostic prints its code. `just gen`
renders it into `docs/rulebook/`. `gen-check` keeps the pages current; no meta spec governs them. Write it as Ruff and Clippy do, for a user who knows their documents, skills and
meta specs, not this package.

- **The summary line states the condition**, about the user's subject.
- **What it does** opens with "Checks for" and the subjects the rule reports, then names the meta spec key
  that sets the limit or states the rule; a rule every governed document is held to says that no key states it,
  and a rule the package states names the external specification and its figure instead. It adds each case a user would not guess: what counts, what does not, how several meta specs combine.
- **Why is this bad?** is a sentence or two on what the condition costs the agent that loads the subject, never
  only that a meta spec forbids it.
- **Example** is the input that breaks the rule, under invented paths, in fenced blocks in each file's language:
  the meta spec excerpt, then the subject. For a rule every governed document is held to, the excerpt is of a
  governing meta spec that states some other rule; for a rule the package states, the subject alone. A long subject
  is cut short with a comment, such as `<!-- ... 1800 more tokens -->`.
- **Use instead** is the same subject fixed, in a fenced block, after at most one sentence naming the change. It never
  raises the limit.
- **An engine condition with several causes** has a section per cause in their place.
- *Known problems* follows only when the rule misfires on a case users meet, and *Deviations from upstream* only
  on a rule with alias codes.
- **Nothing of the implementation.** No section names a tokenizer, a parser, a query, a class or a field. The `Attributes:` block after the sections documents the fields, for the maintainer.

```python
# ❌ Bad — the page describes the machinery: which parser counts, not whether a code block counts
class WordCap(QueriedDocumentRule[Facts]):
    """Compares each section's word count from the Markdown parser with its outline entry's cap.

    ## What it does

    Splits each `SectionWords.text` on whitespace and reports `WordCap` when the count exceeds `cap`.
    """
```

```python
# ✅ Good — the name states what is wrong, and the page speaks of the user's section and meta spec
class SectionTooManyWords(QueriedDocumentRule[Facts]):
    """A section is longer than its word cap allows.

    ## What it does

    Checks for sections longer than the `words` cap their outline entry sets in the structure file.
    Subsections count toward it; fenced code blocks and table rows do not.
    """
```

## Checklist

Before committing:

- [ ] Nothing added to `lorecraft.rules` reads the disk, a view, a query or configuration
- [ ] A new rule names its query and its `judge` takes that query's facts and returns occurrences that name no
      subject; a rule over a document declares its facet in `GOVERNED_BY`
- [ ] A new rule is declared with `@rule` in its own module in its group's subpackage, listed nowhere else
- [ ] Decoding, answering a query, running the rules and rendering stay out of the package
- [ ] A new rule's name states its condition; its class and module spell it
- [ ] A new rule's `message()` is lowercase with the value found against the limit; `children()` puts a
      `Note` at the meta spec that states the rule (the corpus's structure file when no key does; the external
      one, without `at`, when the package states it, or the group's `Note` for a rule over an Agent
      Skills field; none for title rules and rules no meta spec states), then the `Help` and other
      `Note`s
- [ ] A new rule's docstring opens *What it does* with "Checks for", shows the broken and the fixed input under
      *Example* and *Use instead*, or per cause, and names nothing of the implementation; a rule no key states says so, and its
      *Example* shows a governing meta spec's excerpt, then the subject; a rule the package states names the
      external specification and its figure, its *Example* the subject alone

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
