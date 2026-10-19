---
name: "adr-009-rules"
description: "How a rule of the structured checks is declared and identified: one class per rule with its own typed check, codes in groups named after the mechanism that states them, alias codes for rules absorbed from other linters, a removed rule as a type of its own, one registry, and a rulebook generated from the classes. Load when writing, porting, renaming or retiring a rule, or changing its code, group, default level or documentation"
type: "adr"
status: "accepted"
---

# Rules: Declaration and Identity

> [!NOTE]
> Superseded in part: how a rule reads the facts it judges, which a queried rule replaces by naming its query and
> judging the facts it returns. The text below states that design where it spoke of a subject context. The rest of
> this record binds code.

This record is one of three that state how the structured checks of [prd-008](prd-008-structured-checks.md) are
built: [adr-009](adr-009-rules.md) how a rule is declared and identified, [adr-010](adr-010-diagnostics.md) what a
rule reports and how it reaches the user, and [adr-011](adr-011-rules-engine.md) how a run judges subjects.
Requirement identifiers such as `FR-009` cite the PRD, and the terms are those of the [glossary](#glossary) below.

It states the shape of a rule and of the registry, not the rules themselves. Which rules exist, their codes, their
groups and how many there are change release by release; the registry and the rulebook are the authority on them,
and every name, code and prefix below is an example.

## Context

Before this record, a rule was a string literal written where its violation was built, and nothing listed the
rules: some identifiers were built from a repository's own corpora, so the set was open-ended. No rule had a level,
a page that explains it, or an identity a configuration or a suppression could name. The design had to hold every
rule the checks carried, over documents, skills, skill resources and layout entries, and not only a sample one.

## Glossary

The terms are the established linters', so a reader who knows one reads this design and its code without
translating: a rule identified by its type, with a code and a name; levels that configure it;
diagnostics in the shape a language server publishes; help and notes beside a message. For a user the model is
shorter still: the checker reports errors and warnings, and they act on them.

| Term | Meaning |
|---|---|
| **Rule** | What a user reads about and configures: a code, a name, a default level and a rulebook page. In the code it is one class, its declaration and its check |
| **Occurrence** | One instance of a rule: where it fired, with the data of that place; names no subject |
| **Rule code**, **rule name** | Such as `OUT004` and `empty-section`. A code is a rule group's prefix and a number |
| **Rule group** | The rules one mechanism states, under one prefix and title |
| **Rulebook** | The reference manual of the engine's rules, one page per code, generated from the rules' classes |
| **Alias code** | An upstream linter's code for a rule Lorecraft absorbed, such as `MD040`. A rule's code is always Lorecraft's; an alias code only points to it |
| **Removed rule** | A retired code, with the release that removed it and its replacement. Never has an occurrence |
| **Engine condition** | A condition the engine reports before any rule runs, such as an undecodable file: declared like a rule, with no level, and one per kind of fix |
| **Cause** | One case of an engine condition, such as which rule of a structure file cannot be applied: a type in the condition's closed union, held as data of its occurrence |
| **Subject** | What is checked: a document, a skill, a skill resource or a layout entry |
| **Facts** | What a rule's query returns for one decoded subject, a pure function of the primitives it reads, each a query of the database |
| **Meta-spec part** | What part of an item a rule reads from its governing meta specs and declares in its gate |
| **Diagnostic** | An occurrence located at a subject's path, with a severity |
| **Level** | `allow`, `warn` or `deny`: how a rule is configured |
| **Severity** | `error` or `warning`: what a diagnostic carries, and what a user acts on |
| **Label** | Text attached to a location: the primary label says what is wrong there, a secondary one points at a related place |
| **Help**, **note** | A sub-diagnostic: help says how to fix this occurrence, a note gives the context that explains it. Either may point at a location |
| **Location** | A line in the subject, the whole subject when it has no lines, or a place in another file, such as the meta spec. The runner supplies the subject's path |
| **Engine diagnostic** | A diagnostic no rule produced: an engine condition's occurrence, or a warning about the configuration |
| **Coverage** | Which meta-spec parts of a subject no governing layer states. Never a diagnostic |
| **Failure** | What stops Lorecraft from judging at all: raised, and exit code 2 |

## Decision

1. **A rule is one class.** The class is the declaration and the check: its code, name, default level,
   documentation, and the classmethod that judges its subject. One rule has one code, one class and one file. A
   removed rule and an engine condition are types of their own, which no rule can be built as.
2. **One registry**, discovered by a package walk, is the only source of rules. The runner, the rulebook and the
   tests read it. A generated, checked index derived from it, for the command line's edge, is not a second list: it
   is output, as the rulebook is, and the generation check holds it equal to the registry.
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
class EmptySection(QueriedItemRule[SectionFacts]):
    """A section holds no content, under a structure file that forbids empty sections.

    ## What it does
    ## Why is this bad?
    ## Example
    ## Use instead
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 4)
    NAME: ClassVar[RuleName] = RuleName('empty-section')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')
    GATES: ClassVar[Mapping[ItemKind, Gate]] = {ItemKind.DOCUMENT: ByMetaSpec(MetaSpecPart.STRUCTURE)}

    spec: RootRelativePath
    section: str

    def message(self) -> str:
        return f'section `{self.section}` is empty'

    @classmethod
    def judge(cls, facts: SectionFacts) -> tuple[Self, ...]:
        ...
```

- **An instance is one occurrence.** It carries the data of its condition and the context its diagnostic needs,
  as [adr-010-diagnostics](adr-010-diagnostics.md) states, and the meta spec file that states the rule, or none
  for a rule the package states. A rule over a subject with lines carries the line; one over a layout entry
  carries none.
- **An item rule declares its applicability.** Every item rule names its query and maps each kind it judges to a gate.
  A gate names the meta spec part, package or registered schema that permits the rule to run. Shared query facts let
  one rule judge several item kinds without a separate base for each kind.
- **A rule over a document declares the meta spec part it reads** in `GATES`, so the runner gates it on governance;
  the registry rejects an item rule with no gates. The package governs skills, their files and the skill layout, so a
  rule over them declares none.
- **`judge` returns `tuple[Self, ...]`**, so a rule can only report its own occurrence, and the type checker
  rejects one that reports another's. That needs no type parameter anywhere in the engine.
- **The message is rendered from the fields.** The corpus, the field and the section travel as data, not as
  text inside a message (FR-011), so the machine-readable output and a persisted result hold structured values.
- **One rule, one message template.** A rule's `message()` does not branch on a condition. Two conditions a writer
  fixes differently are two rule classes and two codes (FR-012), the established linters' granularity, which identify
  a rule by its violation type. The prefix is the coarse handle: a level set on a prefix covers its whole group,
  and one set on a code tunes one condition. An engine condition is the one exception, stated under
  [Codes, Groups and Life Cycle](#codes-groups-and-life-cycle).
- **The docstring is the documentation**, in fixed sections: *What it does*, *Why is this bad?*, *Example*,
  *Use instead*, and optionally *Known problems* and, for a rule with an alias, *Deviations from upstream*. An
  engine condition with several causes replaces *Example* and *Use instead* with one section per cause, each with
  its example and its fix, so no case goes without the guidance a code of its own would have given it. Nothing
  about a rule is written in a second place.
- **Every rule has a default level** (FR-023), on its class. Until a configuration sets levels, it is the level
  every run uses.
- **`@rule` registers the class** and returns it unchanged.
- **One file per rule.** The class, its docstring and its check sit in one module, in a directory per group.

The established linters keep a rule's check as a function beside its violation type. Here it is a classmethod
of the type, the one departure from their shape, so that a rule is one declaration: a rule in service without a
check is an abstract class, which the registry rejects at load, and a removed rule is not a `Rule` at all.
Since the class is then the rule itself, it is named after the rule rather than after a violation, and each
instance is one occurrence of it.

### Codes, Groups and Life Cycle

- **A code is a group and a number** (FR-009), printed as the group's prefix followed by fixed-width digits. A
  group is declared once, with its prefix and title, beside its rules. A code whose prefix disagrees with its group
  cannot be written.
- **A name is a `RuleName`** (FR-009), a value object by [pattern-value-object](../code/pattern-value-object.md):
  kebab-case, validated on construction. A rule's name is never a bare `str`, and it can never be spelled as a code.
- **A prefix names the mechanism that states the rule** (FR-013), never a subject kind: the frontmatter, the
  sections a structure file states, a length limit, links, the skill layout. A group is added with its first rule,
  and the rulebook lists the groups that exist. One prefix is the engine's own and holds its conditions, never a
  rule.
- **An engine condition is declared like a rule** (FR-020): a code in the engine's group, a name, the release it is
  stable since, a fixed severity and a docstring, registered by `@rule`, so it has a rulebook page and its own test
  cases. It has no level and no `check`: the engine finds it before any rule runs, and no selection or
  configuration can turn it off.
- **An engine condition's code splits by kind of fix, not by case.** A code earns its place when a reader looks it
  up, selects it, configures it or suppresses it; an engine condition can only be looked up, so a second code pays
  only for a different kind of fix, such as restoring access to a path rather than correcting a structure file.
  The cases one kind of fix covers are its causes: a closed union of frozen dataclasses held in a `cause` field,
  and `message()`, the labels and the notes `match` on it, closed by `assert_never`, so an unhandled cause fails
  the type check. The message names the cause and what differs in it, such as the operation refused, the OS reason
  or the rule of the structure file that cannot be applied, as the established linters do with one code for every
  file they cannot read.
- **Every code is Lorecraft's, and an upstream code is an alias code.** A rule ported from another linter keeps a
  Lorecraft code in the group of its mechanism, and lists the upstream codes it answers to in `ALIASES`, each
  naming its linter. A condition that several linters check is one rule with several alias codes, never several
  rules. The rulebook page renders each alias as the rule's provenance, and the lookup command finds a rule by one.
  Output prints the code alone. A one-run selection, and later the configuration and suppression, accept an alias
  code and resolve it to the code, with a warning naming the code to write. Absorbing a linter adds rules and
  aliases, and leaves the registry untouched; a fact its rules need that no query returns yet is a new query
  a rule names, never a change to the runner. Which upstream rules are ported is decided
  rule by rule, outside this design.
- **Documents and skills share the frontmatter codes.** The governing schema and the name the subject is found
  under are data of the facts, so one rule serves both, and a later meta spec for skills retires no code.
- **The set of codes is fixed by the package** (FR-011). A schema field never creates a code.
- **Codes identify the engine's rules alone.** A code spec under `docs/code/`, or any other document that states a
  convention, keeps its kebab-case name and never takes a code.
- **Life cycle is a type.** A rule in service is a rule class, with the release it is stable since. A retired rule
  becomes a `RemovedRule`: its code, its name, the release that removed it, its replacement and its docstring,
  registered by `@rule` in the same file. It is not a `Rule`, so it can never be built as one or reported. Its code
  is never free to reuse (FR-014). Naming it fails, and points to the release and the replacement (FR-015).
- **A rule's releases are `Release` values**, a value object by
  [pattern-value-object](../code/pattern-value-object.md), and immutable literals naming a release that already
  happened to the rule. `AGENTS.md` and the release skill exempt them from the rule against a version literal that
  tracks the current release.
- **The committed rulebook is the audit.** No hand-written central table of codes exists. The registry rejects a
  duplicate, and a reused code shows as a changed page.

### The Registry

The registry follows [pattern-registry](../code/pattern-registry.md). It walks the rules package once, imports
every rule module, and collects every declaration `@rule` registered: rules, removed rules and engine conditions.

- **It rejects at load every declaration the types cannot**: an identity bound twice, a rule with no `check`, a
  declaration left incomplete, a declaration in the wrong group, a replacement no rule has. It propagates an import
  failure. What it checks grows with the declarations, and the registry's own documentation is the list.
- It lists rules in code order.
- It is package data. It reads no workspace, is not a query, and no class from it enters a query result. A
  persisted diagnostic is its code and its fields, read back through the registry.

### The Index

Loading the registry imports every rule module, and through them what the rules read, so a reader that only needs
to know which codes exist would pay for the whole engine. The command line's edge is such a reader: it validates a
selection, resolves a rule by code, name or alias, and lists the rules before any run.

- **The index is derived from the registry** and holds identity alone, as plain data in one generated module,
  with the lookups over it. It holds no class and no type of the engine's, since one would load the engine.
- **A generator outside the published package writes it**, and the generation check fails on a stale index, as on
  a stale rulebook page.
- **It is not a second list.** Nothing declares a rule in it: a rule joins by `@rule`, and the index follows. It is
  never edited by hand.
- **Only the edge reads it.** A run builds its rule table from the registry.

### The Rulebook

The rulebook is the reference manual of the engine's rules: the page a user reads when the checker prints a code
and they want to know what it means and how to fix it. It lives in this repository alone, never in a repository
that uses Lorecraft, and every word of it is generated from the rules' classes.

- **One page per code**, removed rules and engine conditions included (FR-028), rendered by one function from the
  class: the code and name, the release it is stable since, each alias with its upstream linter, then the
  docstring's sections. A removed rule's page states the release that removed it and its replacement.
- **The pages are named by code, then name**, so a listing sorts in code order and each file says what its rule
  is. An alias code has no page: the rule's page lists it, and the lookup resolves it.
- **A generator writes the pages**, and the generation check fails on a stale one. Nothing in the rulebook is
  written by hand, and no meta spec governs it.
- **The listing is the index of the rulebook**, and the command line is the other: it lists every rule in code
  order, and prints one page by code, by name or by alias (FR-029), from the same rendering function, so a user
  without this repository reads the same text.
- **Feat specs link to a page** and restate no rule.

### Tests

- **Per code:** at least one triggering case and one near miss (NFR-006), each a fixture on disk holding the
  repository to check and the diagnostics the checker is expected to report, compared whole.
- **A meta-test over the registry** names every code that lacks either kind of case. It reads the registry and the
  fixtures and runs nothing.
- **An overlap is declared where it occurs.** The comparison is exact, so a second code on a line fails the case
  unless the case's expected diagnostics list it; no separate table of allowed pairs exists.
- **The registry** is tested for each declaration it rejects and for an import failure.
- **A rule's `Release` is checked for its format alone**, by the value object. A well-formed but wrong release is
  the reviewer's to catch.

## Alternatives Considered

- **A function that reports several codes.** One judging function declares a set of violation classes and
  returns any of them. It needs no intermediate problem types. Not chosen: the type checker cannot hold a function
  to a declared set, so the runner would need a membership check, and a rule would no longer be one file. It
  becomes the better choice only if a shared analysis turns expensive.
- **A decorator on a function that returns code-less hits, stamped by the runner.** It was the first proposal.
  The rule class needs no stamping, and it makes a diagnostic structured data.
- **The check as a function beside the class, registered by a generic decorator.** The established linters'
  shape. Class and function are then two declarations tied at runtime: a rule in service can lack its check, and a
  removed rule is still a violation that can be built. The classmethod rejects the first at load, makes the second
  unrepresentable, and removes the engine's only type parameter.
- **"Lint" for the engine's unit, keeping "rule" for what a meta spec or a code spec states.** Not chosen: a
  user acts on errors and warnings, and code rules, the alias of code specs, are the only other "rules" they meet,
  which the context tells apart.
- **An absorbed rule keeps its upstream code**, in a group per upstream linter, as some established linters do.
  Not chosen: a condition two absorbed linters check needs two groups and a choice between their codes, rules sit
  by provenance rather than by mechanism, and the codes stop being one scheme.
- **A hand-written central table of codes.** It splits a rule across two files. It pays off for a linter that ports
  thousands of rules from upstream numbering, which Lorecraft does not have.
- **One code per identifier of v0.2, the condition as data.** Fewer codes, and a `message()` that branches on a kind
  field. Linters that take this shape do so because a rule's options carry the user's specification, so the rule
  must be one. Here the meta spec is data the rule reads, a rule takes no options, and the prefix already gives the
  coarse handle. The coarse code would only cost a page that explains several fixes, conditions that cannot be
  configured apart, and the kind field [python-typing](../code/python-typing.md) rules out. An engine condition
  takes this shape, with a closed union of cause types in place of a kind field: it cannot be configured, so the
  only cost left is the page, which one section per cause pays.
- **One code per engine condition case.** Each way an input can be unusable gets its own code. Not chosen for the
  engine's group: the codes outnumber the kinds of fix several times over, and a code nobody can select, configure
  or suppress buys only a rulebook page that one section per cause gives as well.

## Consequences

- **Every rule took a new identity.** Dotted identifiers became codes, and the release notes carry the mapping.
- **More files, each smaller.** A module per rule replaced v0.2's check modules.
- **The engine's group stays small.** Its codes count kinds of fix, so a new way for an input to be unusable is a
  cause, a rulebook section and a test case, and takes a code only when its fix is of a new kind.
- **Adding, renaming or retiring a rule regenerates the rulebook and the index**, and the generation check holds
  both to the registry.

## Deferred

| Deferred | What the design keeps open |
|---|---|
| Tags | A group that cuts across prefixes, such as every rule a skill can break, would be a tag carried by the class, added without touching a code |
| Alias codes in the machine-readable output | Each diagnostic carries its rule's alias codes beside the code, added with the first rule that declares one |

## Checklist

Before committing code, verify:

- [ ] A new rule is one class in one module of its group's directory, registered by `@rule`, with a code, a name, a
  default level, the release it is stable since, and a `check` classmethod returning `tuple[Self, ...]`
- [ ] A rule's docstring holds *What it does*, *Why is this bad?*, *Example* and *Use instead*, an engine condition
  with several causes holds one section per cause in place of the last two, and nothing about the rule is written
  in a second place
- [ ] A rule's `message()` never branches; a condition fixed differently is another class and another code
- [ ] An engine condition has one code per kind of fix; its cases are a closed union of cause types, matched with
  `assert_never`, and each cause has a test asserting its message
- [ ] A rule over a document declares its gates in `GATES`
- [ ] A code is never reused: a retired rule becomes a `RemovedRule` in the same file
- [ ] A ported rule keeps a Lorecraft code in the group of its mechanism and lists upstream codes in `ALIASES`
- [ ] An engine condition is declared in the engine's group, and no rule is
- [ ] Every code has a triggering case and a near miss
- [ ] The rulebook and the index are regenerated after a rule is added, renamed or retired, or its docstring
  changes, and neither is edited by hand

## References

- [prd-008-structured-checks](prd-008-structured-checks.md) - Source: The requirements this design answers
- [adr-010-diagnostics](adr-010-diagnostics.md) - Related: What a rule reports, and how it reaches the user
- [adr-011-rules-engine](adr-011-rules-engine.md) - Related: How a run judges subjects with the rules
- [pattern-registry](../code/pattern-registry.md) - Foundation: Registration beside the definition
- [pattern-value-object](../code/pattern-value-object.md) - Foundation: A rule's `Release` and `RuleName`
- [adr-015-database](adr-015-database.md) - Related: The database opened with its model, which supersedes adr-004
