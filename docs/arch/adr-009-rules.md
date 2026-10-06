---
name: "adr-009-rules"
description: "How a rule of the structured checks is declared and identified: one class per rule with its own typed check, codes in groups named after the mechanism that states them, alias codes for rules absorbed from other linters, a removed rule as a type of its own, one registry, and a rulebook generated from the classes. Load when writing, porting, renaming or retiring a rule, or changing its code, group, default level or documentation"
type: "adr"
status: "proposed"
---

# Rules: Declaration and Identity

This record is one of three that state how the structured checks of [prd-008](prd-008-structured-checks.md) are
built: [adr-009](adr-009-rules.md) how a rule is declared and identified, [adr-010](adr-010-diagnostics.md) what a
rule reports and how it reaches the user, and [adr-011](adr-011-rules-engine.md) how a run judges subjects.
Requirement identifiers such as `FR-009` cite the PRD, and the terms are those of the [glossary](#glossary) below.
Names of types, modules, codes and prefixes in the sketches are illustrative; the shapes are the decision.

## Context

Today a rule is a string. `Violation.rule` is a literal written where the violation is built, and nothing lists
the rules: six identifier patterns are built from a repository's own corpora, so the set is open-ended. No rule
has a level, a page that explains it, or an identity a configuration or a suppression could name.

The design has to hold what the checks carry today: 25 rules and six identifier patterns built from data, over
documents, skills, skill resources and layout entries. A design that fits a sample rule and not that set is not
the design.

## Glossary

The terms are the established linters', so a reader who knows one reads this design and its code without
translating: a rule identified by its type, with a code and a name; levels that configure it;
diagnostics in the shape a language server publishes; help and notes beside a message. For a user the model is
shorter still: the checker reports errors and warnings, and they act on them.

| Term | Meaning |
|---|---|
| **Rule** | What a user reads about and configures: a code, a name, a default level and a rulebook page. In the code it is one class, its declaration and its check |
| **Occurrence** | One instance of a rule: where it fired, with the data of that place; names no subject |
| **Rule code**, **rule name** | `OUT004` and `empty-section`. A code is a rule group's prefix and a number |
| **Rule group** | The rules one mechanism states, under one prefix and title |
| **Rulebook** | The reference manual of the engine's rules, one page per code in `docs/rulebook/`, generated from the rules' classes |
| **Alias code** | An upstream linter's code for a rule Lorecraft absorbed, such as `MD040`. A rule's code is always Lorecraft's; an alias code only points to it |
| **Removed rule** | A retired code, with the release that removed it and its replacement. Never has an occurrence |
| **Subject** | What is checked: a document, a skill, a skill resource or a layout entry |
| **Context** | The read-only view of one decoded subject a rule asks for the facts it reads, each a query of the database |
| **Facet** | What part of a document a specification governs, which a rule over a document declares it reads |
| **Input** | The one frozen value a rule not yet moved onto a context reads about a subject, built from the database's queries |
| **Diagnostic** | An occurrence located at a subject's path, with a severity |
| **Level** | `allow`, `warn` or `deny`: how a rule is configured |
| **Severity** | `error` or `warning`: what a diagnostic carries, and what a user acts on |
| **Label** | Text attached to a location: the primary label says what is wrong there, a secondary one points at a related place |
| **Help**, **note** | A sub-diagnostic: help says how to fix this occurrence, a note gives the context that explains it. Either may point at a location |
| **Location** | A line in the subject, the whole subject when it has no lines, or a place in another file, such as the specification. The runner supplies the subject's path |
| **Engine diagnostic** | A diagnostic no rule produced: an undecodable file, an error; an alias code in the configuration, a warning |
| **Coverage** | Which facets of a subject no specification governs, and which input kinds while rules still read inputs. Never a diagnostic |
| **Failure** | What stops a run before any subject is checked: raised, and exit code 2 |

## Decision

1. **A rule is one class.** The class is the declaration and the check: its code, name, default level,
   documentation, and the classmethod that judges its input. One rule has one code, one class and one file. A
   removed rule is a type of its own, which can never be reported.
2. **One registry**, discovered by a package walk, is the only list of rules. The runner, the rulebook and the
   tests read it.
3. **The rulebook is generated from the classes**, and the command line prints the same page.
4. **Names follow the established linters**, in the code as in the output, and a departure is stated where it
   occurs.
5. **The design is checked statically**, in this record and the two beside it. Every state it rules out is one
   the type checker rejects: a value that cannot be built, a call that cannot be written, a `match` that
   `assert_never` proves exhaustive. Where Python's types cannot express a rule, the gap is stated where it occurs
   and held by the registry at load or by a test, never left to a convention nobody checks.

## Design

### A Rule Is One Class

```python
@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class EmptySection(HeadingsRule):
    """A section holds no content, under a structure specification that forbids empty sections.

    ## What it does
    ## Why is this bad?
    ## Example
    ## Use instead
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 4)
    NAME: ClassVar[RuleName] = RuleName('empty-section')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')

    spec: RootRelativePath
    section: str

    def message(self) -> str:
        return f'section `{self.section}` is empty'

    def children(self) -> tuple[Subdiagnostic, ...]:
        return (spec_note(self.spec), Help('omit the section rather than leave it empty'))

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

- **`Rule`** carries what every occurrence has: the specification file that states the rule (or none, for a
  rule the package states). The line is not on it: every base whose subject has lines derives from
  `ContentRule`, which carries the line, and `LayoutRule`, for a layout entry, carries none. A subclass
  adds the data of its own condition and the context its diagnostic needs, as
  [adr-010-diagnostics](adr-010-diagnostics.md) states.
- **The base class names the subject kind.** Each subject kind has one base, `DocumentRule` for a document and
  `SkillRule` for a skill, whose abstract `check` takes the subject's context, a `Protocol` of `lorecraft.project`.
  A rule picks its subject by picking its base, and asks the context for what it reads. A rule over a document
  declares the facet it reads in `GOVERNED_BY`, and the registry rejects one that declares none; the package governs
  every skill, so a rule over a skill declares none. No shipped rule derives from these bases yet: each still picks
  an input by its base, such as `HeadingsRule` above, until it moves onto a context.
- **`check` returns `tuple[Self, ...]`**, so a rule can only report its own occurrence, and the type checker
  rejects one that reports another's. That needs no type parameter anywhere in the engine.
- **The message is rendered from the fields.** The corpus, the field and the section travel as data, not as
  text inside a message (FR-011), so the machine-readable output and a persisted result hold structured values.
- **One class, one message template.** `message()` does not branch on a condition. Two conditions a writer
  fixes differently are two classes and two codes. That is the granularity for FR-012, the established linters'
  that identify a rule by its violation type: a missing section, a section out of order and a section past the
  outline's end are three codes, not one. The prefix is the coarse handle: a level set on `OUT` covers the whole
  outline, and one set on a code tunes one condition.
- **The docstring is the documentation**, in fixed sections: *What it does*, *Why is this bad?*, *Example*,
  *Use instead*, and optionally *Known problems* and, for a rule with an alias, *Deviations from upstream*. Nothing
  about a rule is written in a second place.
- **`@rule` registers the class** and returns it unchanged. Its one type parameter only passes the decorated
  class's type through; nothing in the engine is generic over what a rule reads.
- **One file per rule.** The class, its docstring and its check sit in one module, in a directory per group.

The established linters keep a rule's check as a function beside its violation type. Here it is a classmethod
of the type, the one departure from their shape, so that a rule is one declaration: a rule in service without a
check is an abstract class, which the registry rejects at load, and a removed rule is not a `Rule` at all.
Since the class is then the rule itself, it is named after the rule rather than after a violation, and each
instance is one occurrence of it.

### Codes, Groups and Life Cycle

- **A code is a group and a number** (FR-009). `RuleCode(GROUP_ID, 4)` prints as the group's prefix followed by
  zero-padded digits. A group is declared once, with its prefix and title, in its directory's package. A code
  whose prefix disagrees with its group cannot be written.
- **A name is a `RuleName`** (FR-009), a value object by [pattern-value-object](../code/pattern-value-object.md):
  one string field of one or more words of lowercase ASCII letters and digits, joined by single hyphens,
  validated on construction. A rule's name is never a bare `str`, and it can never be spelled as a code.
- **A prefix names the mechanism that states the rule** (FR-013), never a subject kind, and its numbers run in
  sequence:

  | Prefix (illustrative) | Rules |
  |---|---|
  | `FM` | The frontmatter block and its schema |
  | `OUT` | The sections a structure specification states |
  | `LEN` | Every length limit: a document's token budget, a skill's line budget, a section's word cap |
  | `LINK` | Links inside a skill |
  | `LAY` | The skill layout |
  | `LC` | The engine's own conditions, such as an undecodable file, and no rule |

  A group for the Markdown body, such as its blocks or its inline links, is added with its first rule.
- **Every code is Lorecraft's, and an upstream code is an alias code.** The engine absorbs other linters'
  rules: a rule ported from one keeps a Lorecraft code in the group of its mechanism, and lists the upstream
  codes it answers to in `ALIASES`, each naming its linter, such as `MD040` of markdownlint. A condition
  that several linters check is one rule with several alias codes, never several rules. The rulebook page renders
  each alias as the rule's provenance, the lookup command finds a rule by one, and the machine-readable output
  carries them beside the code. Output prints the code alone. Configuration and suppression accept an alias code
  and resolve it to the code, with a warning naming the code to write. Absorbing a linter adds
  rules and aliases, and leaves the registry untouched; a fact its rules need that no context offers yet is a method
  of the context and a query of the database, never a change to the runner. Which upstream rules are ported is
  decided rule by rule, outside this design.
- **Documents and skills share the frontmatter codes.** A skill's frontmatter is judged against the Agent Skills
  schema and a document's against its corpus schemas. The governing schema and the name the subject is found
  under are data of the input, so one rule serves both and a later specifications corpus for skills retires no
  code. A `name` that differs from a document's filename and one that differs from a skill's directory are one
  code.
- **The set of codes is fixed by the package** (FR-011). A schema field never creates a code.
- **Codes identify the engine's rules alone.** A code rule under `docs/code/`, and any rule a repository's own
  documents state, keeps its document's kebab-case name and never takes a code: agents read and apply those
  rules, and the engine reports none of them.
- **Life cycle is a type.** A rule in service is a rule class, with `SINCE`. A retired rule becomes a
  `RemovedRule`: its code, its name, `REMOVED_IN`, `REPLACED_BY` and its docstring, registered by `@rule` in the
  same file. It is not a `Rule`, so it can never be built as one or reported. Its code is never free to
  reuse (FR-014), and a configuration that names it fails with the release and the replacement (FR-015).
- **`SINCE` and `REMOVED_IN` are `Release` values**, a value object by
  [pattern-value-object](../code/pattern-value-object.md): one string field in the form `MAJOR.MINOR.PATCH`,
  digits only, no leading zeros, no `v` prefix and no pre-release or build suffix, validated on construction. A
  rule's release is never a bare `str`.
- **They are immutable literals** naming a release that already happened to the rule. `AGENTS.md` and the
  release skill forbid a version literal that tracks the current release; they gain an exception for these in
  the change that first adds one.
- **The committed rulebook is the audit.** No central table of codes exists. The registry rejects a duplicate,
  and a reused code shows as a changed page.

### The Registry

The registry follows [pattern-registry](../code/pattern-registry.md). It walks the rules package once, imports
every module, and collects the rule classes and removed rules `@rule` registered.

- It rejects a code, an alias code or a name bound twice, and a rule class that is still abstract: a
  rule with no `check`. It propagates an import failure.
- It lists rules in code order.
- It is package data. It reads no workspace, is not a query, and no class from it enters a query result. A
  persisted diagnostic is its code and its fields, read back through the registry.

### The Rulebook

The rulebook is the reference manual of the engine's rules: the page a user reads when the checker prints
`error[OUT006]` and they want to know what it means and how to fix it. It lives in this repository alone, never in
a repository that uses Lorecraft, and every word of it is generated from the rules' classes.

One function renders a rule's page from its class: the code, the name, the prefix, the default level, the
release it is stable since, the docstring's sections, a link to the declaring module, and the rule's origin:
the specification that states it or the package, and each alias with its upstream linter. A removed
rule's page states the release that removed it and its replacement.

```text
docs/rulebook/
├── FM001-missing-frontmatter.md
├── …
├── OUT006-missing-section.md
└── LEN001-too-many-tokens.md
```

- **`docs/rulebook/` is a flat corpus**, one page per code, removed rules included (FR-028). A page is named
  `<code>-<name>.md`, as in `OUT006-missing-section.md`: the code first, the identity a diagnostic prints, so the
  listing sorts in code order, then the rule's kebab-case name, so the file says what the rule is. The page's
  frontmatter `name` is the same `<code>-<name>`, as the corpus convention that `name` matches the filename
  asks. An alias code has no page: the rule's page lists it, and the lookup resolves it.
- **A `gen-*` recipe writes the pages**, and the generation check fails on a stale one. Nothing in the corpus is
  written by hand but its specification, `docs/__meta__/rulebook.md` and its structure, whose outline is the
  docstring's sections.
- **The engine checks its own rulebook.** A rule whose docstring lacks a required section renders a page that
  fails this repository's document gate.
- **The directory listing is the index**, in code order and grouped by prefix; no index document is kept. The
  command line is the other: it lists every rule in code order, and prints one page by code, by name or by alias
  (FR-029), from the same rendering function, so a user without this repository reads the same text.
- **Feature docs link to a page** and restate no rule.

### Tests

- **Per rule:** a triggering case and a near miss, keyed by the code and asserted on the occurrence's type
  (NFR-006).
- **A meta-test over the registry** names every code that lacks either case, and fails when two codes fire on
  one line of a case unless the pair is declared.
- **The registry** is tested for the duplicate and the import failure.
- **A rule's `Release` is checked for its format alone**, by the value object. No test compares it with the
  repository's tags: a well-formed but wrong release is the reviewer's to catch.
- **How a test case is keyed to its code** is left to the change that adds the meta-test.

## Alternatives Considered

- **A function that reports several codes.** One judging function declares a set of violation classes and
  returns any of them, as the link walk reports several identifiers today. It needs no
  intermediate problem types. It was not chosen because the type checker cannot hold a function to a declared
  set, so the runner would need a membership check, and a rule would no longer be one file. It becomes the
  better choice only if a shared analysis turns expensive.
- **A decorator on a function that returns code-less hits, stamped by the runner.** It was the first proposal.
  The rule class needs no stamping, and it makes a diagnostic structured data.
- **The check as a function beside the class, registered by a generic decorator.** The established linters'
  shape, and this design's previous draft. Class and function are then two declarations tied at runtime: a rule
  in service can lack its check, and a removed rule is still a violation that can be built. The classmethod
  rejects the first at load, makes the second unrepresentable, and removes the engine's only type parameter.
- **"Lint" for the engine's unit, keeping "rule" for what a specification or a code rule states.** Not chosen: a
  user acts on errors and warnings, and the code rules are the only other rules they meet, which the context
  tells apart.
- **An absorbed rule keeps its upstream code**, in a group per upstream linter under upstream's prefix, as some
  established linters do. Not chosen: a condition two absorbed linters check needs two groups and a choice
  between their codes, rules sit by provenance rather than by mechanism, and the codes stop being one scheme.
  Alias codes keep the upstream code for recognition, while the code stays Lorecraft's.
- **A central table of codes.** It splits a rule across two files. It pays off for a linter that ports
  thousands of rules from upstream numbering, which Lorecraft does not have.
- **One code per identifier of today, the condition as data.** It gives about 25 codes instead of about 45, and
  a `message()` that branches on a kind field. Linters that take this shape do so because a rule's options carry
  the user's specification, such as the list of required headings, so the rule must be one. Here the
  specification is data the rule reads, a rule takes no options, and the prefix already gives the coarse handle.
  The coarse code would only cost a page that explains several fixes, conditions that cannot be configured
  apart, and the kind field [python-typing](../code/python-typing.md) rules out.

## Consequences

- **Every rule takes a new identity.** Dotted identifiers become codes, and the release notes carry the mapping
  from one to the other. The `just` recipes and CI, the README, the project skills shipped to users and the
  feature docs change with it.
- **More files, each smaller.** About 45 rule modules replace today's check modules.
- **`AGENTS.md` and the release skill gain an exception** for a rule's `Release` literals, in the change that
  first adds one.

## Deferred

| Deferred | What the design keeps open |
|---|---|
| Tags | A group that cuts across prefixes, such as every rule a skill can break, would be a tag carried by the class, added without touching a code |

## References

- [prd-008-structured-checks](prd-008-structured-checks.md) - Source: The requirements this design answers
- [#315](https://github.com/LNSD/lorecraft/issues/315) - Source: The research and the decisions behind it
- [adr-010-diagnostics](adr-010-diagnostics.md) - Related: What a rule reports, and how it reaches the user
- [adr-011-rules-engine](adr-011-rules-engine.md) - Related: How a run judges subjects with the rules
- [pattern-registry](../code/pattern-registry.md) - Foundation: Registration beside the definition
- [pattern-value-object](../code/pattern-value-object.md) - Foundation: A rule's `Release` and `RuleName`
