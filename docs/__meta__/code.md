---
name: "code"
description: "Code rules documentation format specification. Load when creating or editing rule documents in docs/code/"
type: "meta"
scope: "global"
---

# Code Rules Documentation Format

**MANDATORY for ALL rule documents in `docs/code/`**

## Table of Contents

1. [Core Principles](#1-core-principles)
2. [Frontmatter Requirements](#2-frontmatter-requirements)
3. [Naming Schema](#3-naming-schema)
4. [Cross-Reference Rules](#4-cross-reference-rules)
5. [Document Structure](#5-document-structure)
6. [Content Guidelines](#6-content-guidelines)
7. [Template](#7-template)
8. [Checklist](#8-checklist)

---

## 1. Core Principles

The corpus in `docs/code/` is **the code rules**, also called the code guidelines; the two names mean the same thing, and a single member of it is a **rule document**.

### Rule Documents Are Authoritative

**CRITICAL**: The code rules are the **ground truth** for how code should be written.

- If a rule document exists, the implementation **MUST** follow it
- If code diverges from a documented rule, the code is wrong OR the rule must be updated
- Engineers **MUST** keep rule documents accurate - outdated rules are unacceptable
- When rules evolve, update the rule document in the same change

### Rules Describe This Codebase

Rule documents describe conventions that **exist in `packages/*/src/`**, not conventions imported from other ecosystems or aspirational ones.

- Before writing a rule, find the code that already demonstrates it — then write the example from scratch, without citing that code ([§6](#6-content-guidelines))
- Do not document tooling the repository does not use
- If a rule proposes a new convention, apply it to the code in the same change

The demonstrator is a check the **author** performs, not a citation the **doc** carries. A convention nothing demonstrates is not a convention this repository has; a doc that proves it by quoting a module has merely made a copy that will drift.

### One Document, One Responsibility

**A rule document has exactly one reason to change.** The Single Responsibility Principle applies to these documents as it does to the modules they govern.

Decide a rule's home by asking what would force it to be rewritten:

| The rule changes when…          | It belongs in…                   |
|---------------------------------|----------------------------------|
| Declaration syntax changes      | The group's declaration document |
| A call-time API changes         | The group's usage document       |
| A naming convention changes     | `python-naming`                  |
| The build or manifest changes   | The `python-*` document that owns `pyproject.toml` |
| A third-party signature changes | The document that owns that seam |

**Each rule has exactly one home.** Siblings **link**; they do not restate. A rule stated in two docs has two places to rot and no authority when they disagree — the reader cannot tell which one is stale. Cross-reference with a one-line pointer instead of repeating the rule or its example.

A group's parent doc (`python-modules`, `logging`) is itself a **rule document with content**, not an index. Do not add a doc whose only job is to route to its siblings: frontmatter discovery already does that, and a hand-maintained routing table is a second source of truth that goes stale silently.

### A Group's Prefix Names Its Subject

A rule filed under a prefix must be **about that subject**. `python-errors-*` is about how this project declares and surfaces exceptions; a rule that merely _raises_ one does not belong there. Ask what the rule is about, not what it touches — a doc about rendering findings into a report is about reports, however much `dataclasses` appears in it.

### Rules Are Conventions, Not Module Facts

`docs/code/` carries conventions that **generalize across the project**. A rule that applies to exactly one module or one third-party seam is not a convention: it is a fact about that code, and it belongs **in that code** — a module-level docstring, or an inline comment at the declaration, both governed by the `python-docstrings` group.

The test is where a reader needs it. Someone editing the section-outline checker is looking at that checker's module, not searching `docs/code/` — so the invariant the Markdown parser forces on it, and the comment that must accompany it, are documented at the declaration. A rule that restates a single module's contract is a copy that drifts from the code it describes.

Promote a module fact to a rule only when it recurs across packages and a reader must apply it to code they have not seen yet.

### Rule Documents State Rules, Not Records

**A rule document states the rule in the imperative present.** It is not a record of how the codebase got here.

Write "untrusted input is validated at the boundary", not "we are adopting X" or "this replaces the hand-written guards we used to carry". Migration narrative, the case for a past decision, and rebuttals of the alternatives are **commit messages and PR descriptions**, not rules. A reader arriving in a year needs to know what to type, not what was argued.

Rules must be **independent of project status** — anything true only of today's snapshot rots silently, because nobody re-checks a doc. Keep these **out** of `docs/code/`:

| Do not document                                     | Because                                          | Put it in                     |
|-----------------------------------------------------|--------------------------------------------------|-------------------------------|
| Dependency versions, pins, beta/release status      | Changes on every upgrade                         | Commit message or PR description |
| Benchmark figures and measured timings              | Measured once, on one machine, never re-measured | Commit message or PR description |
| Whether a tool is installed, or its install command | Setup state, not a coding rule                   | Commit message or PR description |
| An inventory of every site a rule applies to        | Must be edited whenever a site is added          | One fabricated example        |

**Enumerating every instance** of a convention is an inventory, and an inventory is a maintenance burden that a rule document does not need: show one fabricated example and state the test the reader applies to their own case.

Linking to an external source (a paper, a spec, a canonical blog post) is fine — see the `External References` section in the `principle-*` docs. Linking to a dependency's release notes, migration map, or install instructions is status.

### A Document's Path Selects Its Specification

Nothing registers a rule document with a specification: the document's own path resolves it.

- A document at `docs/<corpus>/<name>.md` is governed by `docs/__meta__/<corpus>.md`, the **corpus
  specification**, which applies to every document directly in that directory; the checks ignore a
  subdirectory, and §3 forbids one.
- It is **additionally** governed by every `docs/__meta__/<corpus>-<namespace>.md` whose namespace equals the
  document's name or is a hyphen-delimited prefix of it; `code-python-errors.md`, if it existed, would govern
  `python-errors.md` and `python-errors-*.md`. So `docs/code/principle-least-surprise.md` answers to `code.md`
  and to `code-principle.md`.
- **The layers stack, broad to narrow.** The corpus specification is a whole rule set applied on its own; the
  namespace specification states only what it adds or narrows, and it cannot release a document from what the
  corpus specification already said. That is what a namespace specification is for: a rule that holds for a
  group but not for the corpus goes there, and stays out of the corpus file rather than becoming a condition
  inside it.
- **A namespace is a group only once a specification names it.** Documents no `code-<namespace>.md` matches,
  `test-*` and the unprefixed `logging` today, are governed by `code.md` alone. That is the normal case, not a
  gap to fill. Add a namespace specification when a group's members genuinely share rules the rest of the
  corpus does not.
- **Matching is by name and nothing else.** A specification starts governing the moment its name resolves, and
  a group renamed under `docs/code/` stops matching the specification it used to — rename both in the same
  change.

Read the relationship in either direction from the shell:

```bash
ls docs/code/<namespace>.md docs/code/<namespace>-*.md   # from a specification, the documents it governs
ls docs/__meta__/code*                                    # from a document, the specifications that govern it
```

### Discoverability Through Frontmatter

Rule documents use YAML frontmatter for lazy loading - AI agents query frontmatter to determine which rules to load based on the current task context.

### Consistency and Machine Readability

This format specification ensures:

- **Uniform structure** across all rule documents
- **Machine-readable metadata** for automated discovery
- **Clear categorization** via rule types and scopes for organized access
- **Scalability** - easy to add new rules following established format

### Avoid Context Bloat

Keep rule documents focused and concise. Agent entrypoint docs should NOT hardcode rule lists - use dynamic discovery instead.

---

## 2. Frontmatter Requirements

This section is the operative rule, and [code.header.json](code.header.json) beside it is the same rule in a
form a checker applies — `lorecraft check header` validates every document's frontmatter against it, and
`just check-docs` runs that over this corpus. A `principle-*`, `pattern-*`, or `python-*` document is additionally
narrowed by every `code-<namespace>.md` specification whose namespace matches its name
([§1](#1-core-principles)); the narrowing adds to what this section requires and never relaxes it.

**CRITICAL**: Every rule document MUST begin with valid YAML frontmatter:

```yaml
---
name: "rule-name-kebab-case"
description: "Brief description. Load when [trigger conditions]"
type: "principle|core|arch|pkg|meta"
scope: "global|pkg:<name>"
---
```

### Field Requirements

| Field         | Required | Format                       | Description                                                            |
|---------------|----------|------------------------------|------------------------------------------------------------------------|
| `name`        | YES      | `^[a-z0-9]+(-[a-z0-9]+)*$`   | Unique identifier matching filename (minus .md)                        |
| `description` | YES      | Single line, succinct        | Discovery-optimized description (see Description Guidelines below)     |
| `type`        | YES      | `principle`, `core`, `arch`, `pkg`, or `meta` | Rule category (see Type Definitions below)              |
| `scope`       | YES      | `^(global\|pkg:[a-z_][a-z0-9_]*(\.[a-z_][a-z0-9_]*)*)$` | Application scope: global or package-specific |

**All four values are double-quoted**, as the block above writes them. YAML accepts a bare `type: core`, so
the two forms coexist happily and drift apart silently; one form means a diff on the field is always a change
of value, never a change of style.

### Type Definitions

| Type   | Purpose                          | Scope           | Characteristics                                      |
|--------|----------------------------------|-----------------|------------------------------------------------------|
| `principle` | Universal software principles | Always `global` | Best practices for optimal code quality              |
| `core` | Fundamental coding patterns      | Always `global` | Applicable across entire codebase                    |
| `arch` | Architectural patterns           | Always `global` | High-level organizational and structural patterns    |
| `pkg`  | Package-specific patterns        | `pkg:<name>`    | Patterns for individual packages or modules          |
| `meta` | Documentation about documentation| Always `global` | Format specifications and conventions                |

#### `principle` - Principle Rules

Universal software principles and best practices for optimal code quality. These are language-agnostic design principles that guide all implementation decisions.

The `principle-*` prefix is reserved for them, and they follow the `code-principle.md` template. A rule that
only holds for one language, one layer, or one dependency is not a principle.

#### `core` - Core Rules

Fundamental coding standards applicable across the entire codebase: how exceptions are raised and reported, how
modules and imports are laid out, how code is documented, how tests are organized, how logging is written.
Most rules are `core`.

#### `arch` - Architectural Rules

High-level organizational and structural rules — the shape of the distribution, the contents of
`pyproject.toml`, the layout a package follows. An `arch` rule governs where code lives rather than how it is
written.

**`arch` is reserved and currently unused.** No document in the corpus carries it; the first one would govern
the workspace's `pyproject.toml` files and the layout under `packages/`.

#### `pkg` - Package-Specific Rules

Rules scoped to individual packages, using the `pkg-` prefix followed by the package's full import path. The
workspace has two import packages, `lorecraft_core` and `lorecraft`, and both can hold a subpackage of the same
name, so the import package is always part of the name: a doc governing `lorecraft_core/checks/` is scoped
`pkg:lorecraft_core.checks`. A security companion takes the same name plus `-security`.

`scope` carries the import path exactly as Python spells it — **snake_case**, dotted for nesting:
`pkg:lorecraft_core.checks.frontmatter` for a `frontmatter` subpackage of `checks`. The **filename** cannot
carry an underscore or a dot, so it converts both to `-`: a doc scoped `pkg:lorecraft_core.checks` is named
`pkg-lorecraft-core-checks.md`.

A document governing a family of sibling subpackages names the family, not one member.

Reach for this type only when a rule genuinely cannot generalize; a fact about a single module belongs in that
module, not in `docs/code/` ([§1](#1-core-principles)).

#### `meta` - Meta Rules

Documentation format specifications — this document and the per-kind templates that extend it. Meta rules
live in `docs/__meta__/`, not `docs/code/`, and are the only type that may reference each other.

### Type and Scope Are Paired

The two fields are not independent. A document that breaks one of these pairings is malformed:

| Constraint | Meaning |
|------------|---------|
| `type: principle`, `core`, or `arch` | ⇒ `scope: "global"` |
| `type: pkg` | ⇒ `scope: "pkg:<name>"` |
| `name: pkg-<x>` | ⇔ `type: pkg` (a `pkg-` name implies the type, and the type implies the name) |
| `type: meta` | ⇒ `scope: "global"`, and the file lives in `docs/__meta__/` |

### Description Guidelines

Write descriptions optimized for dynamic discovery. Unlike skills (which are executed), rule documents are loaded to guide implementation. Your description must answer two questions:

1. **What does this document explain?** - List specific rules or concepts covered
2. **When should an agent load it?** - Include trigger terms via a "Load when" clause

**Requirements:**
- Written in third person (no "I" or "you")
- Include a "Load when" clause with trigger conditions
- Be specific - avoid vague words like "overview", "various", "handles"
- No ending period

**Examples:**
- ✅ `"Module organization under packages/*/src. Load when creating modules or organizing Python packages"`
- ✅ `"Exception handling patterns, bare-except prohibition. Load when raising or catching exceptions"`
- ✅ `"Frozen dataclass defaults and field ordering. Load when declaring a dataclass"`
- ❌ `"Module organization patterns"` (missing "Load when" trigger)
- ❌ `"This document describes error handling"` (too verbose, missing trigger)
- ❌ `"Rules for testing"` (too vague, missing trigger)

### Discovery Command

The discovery command extracts the frontmatter fields of every rule document for lazy loading:

```bash
grep -m 3 -E '^(description|type|scope):' docs/code/*.md
```

---

## 3. Naming Schema

**Principle:** prefix = group. Files sharing the same first kebab-case segment form a discoverable group.

**Format:** `<prefix>-<aspect>.md`

### Group Shape

**This document does not list the rule documents.** The corpus is discovered by reading frontmatter (see
[§2](#2-frontmatter-requirements)); an inventory here would be a second source of truth that goes stale on the
first rename, and nothing would fail when it did.

What the schema fixes is the **shape**. A group is a prefix, a member adds one segment of specificity, and a
member that specializes another adds a further segment:

```
<prefix>-*                   # the group: everything sharing a first segment
├── <prefix>-<aspect>        # a member of the group
│   └── <prefix>-<aspect>-<facet>   # a member that specializes its parent
└── <prefix>-<aspect>
```

The groups in use are `principle-*` (universal principles), `pattern-*` (design patterns), `python-*`
(language conventions), `python-errors-*`, `test-*`, and unprefixed standalone documents such as `logging`. A
rule document that fits none of them is standalone, and a new group is created by writing its first member.

### A Prefix Names The Subject, Not The Language

A doc's prefix names **what the doc is about**. That is why `logging` and `test-*` carry no `python-` prefix
and are not defects: a doc about the shape of a log line is about logging, and a doc about how tests are
organized is about tests. Prefixing them `python-logging` and `python-test-files` would file them under a
subject they are not about, and would claim the `python-*` group owns everything written in Python — which is
everything.

The `python-*` group is reserved for rules whose subject genuinely **is** the language and its tooling: how a
type annotation is spelled, how modules and imports are laid out, how `pyproject.toml` is written. Only one
language prefix exists in this repository, so there is nothing to disambiguate it against.

Specialization nests by name, not by directory: a `python-modules-imports` would refine `python-modules`, and
a `python-docstrings-params` would refine `python-docstrings`. The parent is a rule document with its own
content, never a router to its children.

### Naming Rules

1. **Use kebab-case** - All lowercase, words separated by hyphens
2. **Prefix = group** - Shared first segment = same group
3. **Progressively specific** - Add specificity per segment
4. **Match filename** - `name` in frontmatter MUST match filename (minus `.md`)
5. **Flat directory** - All files at `docs/code/` root (no subdirectories)
6. **Package patterns** - Use the `pkg-` prefix followed by the package's full import path, with
   underscores and dots converted to hyphens

### Benefits

- **Discoverable** - Searching a prefix finds all related rule documents
- **Grouped** - Related documents sort together alphabetically
- **Scalable** - Easy to add new documents within a group
- **Organized** - Natural grouping when listing files

---

## 4. Cross-Reference Rules

Rule documents may reference other rule documents to establish relationships. Cross-references use defined relationship types and follow directional rules based on document type.

### Relationship Types

| Type | Meaning | Example |
|---|---|---|
| `Related` | Sibling in same prefix group | test-organization <-> test-functions |
| `Foundation` | Core rule a pkg/arch rule builds on | pkg-lorecraft-core-checks -> python-exceptions |
| `Companion` | Paired doc for same package | pkg-lorecraft-core-checks <-> pkg-lorecraft-core-checks-security |
| `Extends` | Specializes/refines another rule document | python-errors-handling -> python-exceptions |

### Direction Rules

| From Type | Can Link To |
|---|---|
| `principle` | Other principle patterns (`Related`) |
| `core` | Principle patterns (`Foundation`), other core patterns (`Related`, `Extends`) |
| `arch` | Principle/core patterns (`Foundation`), other arch patterns (`Related`) |
| `pkg` | Principle/core/arch patterns (`Foundation`), own companion (`Companion`), a pkg doc it specializes (`Extends`) |
| `meta` | Other meta rules only (`Extends`) |

**Key principles:**
- Principle rules are standalone and link laterally to other principle rules
- Core rules link laterally to related or parent core rules, and may reference principle rules as foundation
- Arch rules reference the principle/core rules they build on
- Package rules reference the principle/core/arch rules they depend on, plus a companion or the package doc they specialize
- Meta rules only reference the base format spec they extend

### References Section Format

```markdown
## References
- [python-exceptions](python-exceptions.md) - Extends: Exception type declaration
- [python-modules](python-modules.md) - Foundation: Module organization
- [pkg-lorecraft-core-checks-security](pkg-lorecraft-core-checks-security.md) - Companion: Security checklist
```

### Examples

- ✅ `python-errors-handling` -> `python-exceptions` (Extends: core to core)
- ✅ `pkg-lorecraft-core-checks` -> `python-exceptions` (Foundation: pkg to core)
- ✅ `pkg-lorecraft-core-checks-frontmatter` -> `pkg-lorecraft-core-checks` (Extends: pkg to pkg)
- ✅ `pkg-lorecraft-core-checks` <-> `pkg-lorecraft-core-checks-security` (Companion: bidirectional)
- ✅ an `arch` doc governing `pyproject.toml` -> `python-modules` (Foundation: arch to core)
- ✅ `test-organization` <-> `test-functions` (Related: core siblings)
- ❌ `code` -> `python-modules` (meta rules only reference other meta rules)
- ❌ `python-modules` -> `pkg-lorecraft-core-checks` (core cannot reference pkg rules)

---

## 5. Document Structure

### Required Sections

[code.structure.json](code.structure.json) beside this file holds the outline below in machine-checkable
form, and `check_structure.py` applies it. A
`principle-*`, `pattern-*`, or `python-*` document takes its section outline from the narrowest
`code-<namespace>.md` specification that matches its name instead of the general shape below; the general
shape governs every document no namespace specification matches, `test-*` and `logging` today
([§1](#1-core-principles)).

Every rule document should follow this general structure:

| Section | Required | Description |
|---------|:--------:|-------------|
| H1 Title | Yes | Human-readable document title |
| Scope line | Optional | Bold line naming what the document governs; written only where `scope` cannot say it |
| Main content sections | Yes | Rule content organized by topic |
| Checklist | Yes | Verification checklist for rule compliance |
| References | No | Cross-references to related rule documents (follow type rules) |
| External References | No | Links to external articles, books, or specs |

**The order above is the order on the page.** The Checklist is the last thing a reader *does* in the
document; References and External References are navigation away from it, and they are a pair that stays
adjacent. A document that puts References before the Checklist splits that pair the moment it gains an
External References section.

### The Scope Line Is Written Only When It Narrows

A bold line under the H1 is warranted **only when it says something the `scope` field cannot**. Every rule
document is mandatory — [§1](#1-core-principles) establishes that for the whole corpus — so a line announcing
that a `scope: "global"` document applies to all code states three facts already stated by the frontmatter,
the title, and the corpus's own authority. It is ceremony, and ceremony drifts: it is not read, so nobody
notices when it stops matching.

Write the line when the document governs **less than its `scope` implies** — a kind of item, a file type, a
subset of packages, a decision point:

```markdown
✅ Governs something `scope` cannot express
**MANDATORY for ALL test modules under `packages/*/tests/it/`**
**MANDATORY for ALL `pyproject.toml` files in the project**
**MANDATORY for ALL dataclasses declared in the project**

❌ Restates `scope: "global"` and the corpus-wide mandate
**MANDATORY for ALL Python code in the project**
**MANDATORY for ALL code in the project**
```

Where the line is written, the scope phrase is **"in the project"**, never a product name: a product name
carries no scope information and does not survive a rename. Where it is not written, the H1 and the `scope`
field carry the whole answer.

### Optional Sections

Include when relevant:

- **Table of Contents** - For lengthy documents
- **Complete Examples** - Comprehensive usage examples
- **Configuration** - Setup and configuration guidance

**CRITICAL**: No empty sections allowed. If you include a section header, it must have content. Omit optional sections entirely rather than leaving them empty.

---

## 6. Content Guidelines

### Code Examples Are Illustrations, Not Citations

**Every example is fabricated, and no example cites a module.** An example exists to _illustrate_ the
rule the doc states — the least code that carries the convention, invented for the purpose, standing
on its own.

This is deliberate, and it is the opposite of what a citation buys. A `# ✅ Good — lorecraft_core/x/y.py`
attribution makes a doc feel checkable, but it is a **copy of a module living in a second file**, and
it rots exactly like any other copy: the package is renamed, the helper moves, the signature grows an
argument, the code the doc quotes is deleted — and now the rule document is wrong about the repository
in a way nobody notices, because nobody re-reads a doc when they edit the code it quotes.

A fabricated example cannot drift, because it makes no claim about the codebase. It says "here is
what the rule looks like", not "here is where the rule lives" — and only the first of those is the
doc's job.

So:

- **Never write a file path into an example**, in the `# ✅ Good —` comment or anywhere else. The
  comment says _why_ the example is good or bad, never _where_ it came from.
- **Never assert, in prose, that a named module does the thing.** "`lorecraft_core/checks/base.py`
  states X" is a citation wearing a sentence, and it rots on the next rename. State the rule.
- **Invent the names.** Illustrative subjects (`parse_frontmatter`, `OutlineSpec`, `load_corpus`) are
  preferred precisely because they are obviously not an inventory of the project.
- **Stay as close to the real code as the rule allows.** Fabricated does not mean generic. An example should
  look like something this project would plausibly contain — the same domain vocabulary, the same shapes,
  the same exception types, the same threading style — so a reader recognizes their own code in it. `foo`/`bar`
  and toy domains (shapes, animals, a restaurant) teach nothing, because the reader has to translate before they
  can apply the rule, and the translation is where the rule gets lost. Write the example you would have
  written had you been solving the real problem, then rename everything.

Three things stay exact, because they are what the doc is teaching rather than evidence for it:

- **Third-party and stdlib APIs**: `pathlib.Path`, `dataclasses.dataclass`, `logging`, `re`, `tomllib`.
  A doc that gets these wrong teaches the wrong thing.
- **The names of packages and subpackages.** `lorecraft_core`, `lorecraft` and the subpackages declared
  under them — written as they really are, never disguised. These are the project's vocabulary,
  and a reader who cannot map an example onto the package it concerns has to translate before they can
  apply the rule, which is the same cost a toy domain imposes. Invented substitutes are at their worst
  in a doc whose subject **is** naming, where the fabrication defeats the lesson. What must not follow
  the name is the package's **API**: do not import its types or reproduce its signatures, because those
  drift and the name does not.
- **A subpackage that a rule names as its subject.** A rule that says "every checker returns findings
  rather than raising" is stating the convention, not citing a module. The test is whether the name is
  the **rule** or the **proof**. Evidence rots; a rule is what the reader came for.

A fabricated example is still written in this project's stack and style: it passes the project's Ruff
configuration, and it never demonstrates tooling the repository does not use.

Naming a **path pattern** is not a citation and stays allowed, because it is the convention itself:
`packages/*/src/<import package>/<pkg>/`, `packages/*/src/<import package>/<pkg>/tests/test_*.py`, `__init__.py`. What is banned is pointing at one real module
as evidence.

The `Good` / `Bad` pair still carries the argument. A **Bad** example is the mistake the rule exists
to prevent, and it is at its strongest when it names the cost concretely — "this raised on every
document with an empty frontmatter block and no test noticed" teaches more than a bare `foo`. Invent
the war story if you must, but keep it specific: the point is the failure mode, not the provenance.

**A convention must still exist in `packages/*/src/` to be documented** ([§1](#1-core-principles)) — that
requirement is unchanged, and it is on the _author_ to have verified it. What changed is that the doc
no longer proves it by quoting a file, because that proof expires.

### Examples Are Labelled With One of Three Markers

Every example opens with a comment naming its verdict, using one of exactly three markers:

| Marker | Means                                                                 |
|--------|------------------------------------------------------------------------|
| `# ✅ Good —` | This is the form to write                                       |
| `# ❌ Bad —`  | This is the mistake the rule exists to prevent                  |
| `# 🔶 Acceptable —` | Permitted under a stated condition, not the default       |

The emoji is the point: it is scannable in a long document, survives being pasted into a review comment, and
reads at a glance in a rendered page where a bare `# Good` disappears into the code. Three markers is the
whole vocabulary — no fourth verdict, and no `CORRECT`/`WRONG` shouting.

The em dash is followed by the reason, never a restatement of the verdict: `# ❌ Bad — this silently drops
every finding after the first one in a section` says something; `# ❌ Bad — wrong` does not. What that clause
must contain is governed above: the failure mode and what it cost, never where the code came from.

### DO

- Keep rules focused and actionable
- Label every example `# ✅ Good —`, `# ❌ Bad —`, or `# 🔶 Acceptable —`
- Include code snippets showing correct and incorrect usage, in Python
- Fabricate every example: the least invented code that carries the convention
- Verify a real module demonstrates the convention before documenting it — then write the example from scratch
- Name path patterns (`packages/*/src/<import package>/<pkg>/`, `packages/*/src/<import package>/<pkg>/tests/test_*.py`) where the convention is about layout
- Use consistent terminology throughout
- Include a verification checklist at the end
- Explain the reasoning behind rules

### DON'T

- Duplicate content from feature docs (link instead)
- Restate a rule that another document already owns (link instead)
- Restate a single module's contract (document it in that module instead)
- Cite a module in an example, or point at one in prose as evidence (it is a copy, and it drifts on the next rename)
- Transcribe real code into an example, verbatim or lightly edited
- Document a convention no package in `packages/*/src/` demonstrates (a convention nothing demonstrates is not one)
- File a rule under a prefix whose subject it is not
- Cover more than one responsibility in a doc, or add a doc that only routes to its siblings
- Narrate a migration, or argue the case for a decision already made
- Record dependency versions, release/beta status, benchmark figures, or tool install state
- Inventory every site a rule applies to (show one fabricated example instead)
- Include project-specific business logic
- Hardcode paths that may change frequently
- Add speculative or planned rules
- Document tooling the project does not use
- Use vague descriptions ("various", "multiple", "etc.")
- Leave optional sections empty (omit them instead)

---

## 7. Template

Use this template when creating new rule documents:

````markdown
---
name: "{{rule-name-kebab-case}}"
description: "{{Brief summary. Load when [trigger conditions], no period}}"
type: "{{principle|core|arch|pkg|meta}}"
scope: "{{global or pkg:<name>}}"
---

# {{Document Title - Human Readable}}

**MANDATORY for {{what this governs}}** {{OPTIONAL - only where `scope` cannot say it; omit otherwise}}

## Table of Contents {{OPTIONAL - for lengthy documents}}

1. [Section Name](#section-name)
2. [Another Section](#another-section)
3. [Checklist](#checklist)

## {{Main Content Sections}}

{{Rule content organized by topic.
Include code examples showing correct and incorrect usage.
Every example is fabricated; name no module.}}

### {{Subsection}}

{{Detailed guidance with examples:}}

```python
# ❌ Bad — {{what went wrong, and what it cost when it shipped}}
{{incorrect_example()}}
```

```python
# ✅ Good — {{why this is right, and what it prevents}}
{{correct_example()}}
```

The Good example is **fabricated**: it shows the least invented code that carries the convention, and
it names no module ([§6](#6-content-guidelines)). The comment says why, never where.

## Checklist

Before committing code, verify:

- [ ] {{Verification item 1}}
- [ ] {{Verification item 2}}
- [ ] {{Verification item 3}}

## References {{OPTIONAL - follow cross-reference rules}}

- [rule-name](rule-name.md) - Relationship: Brief description

## External References {{OPTIONAL}}

- [{{External reference title}}]({{url}})
````

---

## 8. Checklist

Before committing a rule document:

### Frontmatter

- [ ] Valid YAML frontmatter with opening and closing `---`
- [ ] `name` is kebab-case and matches filename (minus .md)
- [ ] `type` is one of: `principle`, `core`, `arch`, `pkg`, `meta`
- [ ] `scope` is valid: `global` or `pkg:<name>` (snake_case, dotted for nesting)
- [ ] `type` and `scope` are paired as [§2](#2-frontmatter-requirements) requires
- [ ] `description` includes "Load when" trigger clause (no ending period)
- [ ] Frontmatter is valid YAML (no syntax errors)

### Structure

- [ ] H1 title (human readable) after frontmatter
- [ ] A scope line appears only if it narrows what `scope` already says; if present, it reads "in the
      project" rather than naming a product
- [ ] Main content sections with rule details
- [ ] Checklist section for verification
- [ ] No empty sections (omit optional sections rather than leaving them empty)

### Naming and Organization

- [ ] File located at `docs/code/` root (no subdirectories)
- [ ] Filename uses kebab-case
- [ ] Filename uses appropriate prefix for its group
- [ ] Related documents share the same prefix
- [ ] Package-specific documents follow `pkg-<package-name>.md` format
- [ ] Internal cross-references use correct paths

### Cross-References

- [ ] References use defined relationship types (`Related`, `Foundation`, `Companion`, `Extends`)
- [ ] Package rules reference foundation core rules
- [ ] Security companions are bidirectionally linked
- [ ] Meta rules only reference other meta rules

### Content

- [ ] Every convention documented is demonstrated by code in `packages/*/src/` (the author checked; the doc does not cite it)
- [ ] Code examples are Python and pass the project's Ruff configuration
- [ ] Every example is fabricated — no example cites a module, and no prose points at one as evidence
- [ ] Every example is labelled `# ✅ Good —`, `# ❌ Bad —`, or `# 🔶 Acceptable —`, with the reason after the dash
- [ ] No example is a transcription of real code, and a rename anywhere in `packages/*/src/` could not falsify the doc
- [ ] Examples use this project's domain vocabulary and idioms, not toy domains a reader must translate
- [ ] The doc states rules and shows shapes; it does not enumerate the documents that exist
- [ ] Path patterns (`packages/*/src/<import package>/<pkg>/`, `packages/*/src/<import package>/<pkg>/tests/test_*.py`) appear only where the convention is about layout
- [ ] No rule assumes tooling the project does not have

### Responsibility and Durability

- [ ] The doc has one responsibility — a single reason to change
- [ ] Every rule in it is about the subject its prefix names, not merely something that touches it
- [ ] Every rule generalizes across the project; a fact about one module or seam is documented in that module
- [ ] Every rule in it has exactly one home; siblings are linked, not restated
- [ ] The doc carries rule content (it is not a routing index for its group)
- [ ] Rules are stated in the imperative present, not as migration narrative or as the case for a past decision
- [ ] No dependency version, beta/release status, benchmark figure, or tool install state appears
- [ ] Conventions show one example rather than enumerating every site they apply to

### Discovery

- [ ] Description is optimized for AI agent discovery
- [ ] The document is found by the discovery command in [§2](#2-frontmatter-requirements)
- [ ] Trigger conditions are clear and specific

### Review

`just check-docs` decides the frontmatter, section and length items; read the rest of this checklist by hand,
together with every `code-<namespace>.md` specification that matches the document's name.
