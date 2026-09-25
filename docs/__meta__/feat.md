---
name: "feat"
description: "Feature documentation format specification. Load when creating or editing feature docs in docs/feat/"
type: "meta"
scope: "global"
---

# Feature Documentation Format

**MANDATORY for ALL feature documents in `docs/feat/`**

## Table of Contents

1. [Core Principles](#1-core-principles)
2. [Frontmatter Requirements](#2-frontmatter-requirements)
3. [Naming Schema](#3-naming-schema)
4. [Document Structure](#4-document-structure)
5. [Content Guidelines](#5-content-guidelines)
6. [Prose Budget](#6-prose-budget)
7. [Template](#7-template)
8. [Checklist](#8-checklist)

---

## 1. Core Principles

The corpus in `docs/feat/` is **the feature documentation**; a single member of it is a **feature document**.
A feature document describes something this toolkit provides — a check, a specification dialect, a corpus, a
command surface — at the level a reader needs to use it, not at the level a reader needs to modify it.

### The Corpus Starts Empty

`docs/feat/` holds no documents today, and that is deliberate. This repository documents its own features
there as it builds them: the first feature document lands in the same change as the first check that ships.
A `.gitkeep` keeps the directory in the tree so the corpus has a home before it has members, and so this
specification and its three machine-readable companions can be read, reviewed and applied on the day the
first document arrives rather than written in a hurry alongside it.

Do not seed the corpus with documents for features that do not exist. A feature document describing
unimplemented behaviour is indistinguishable from a feature document describing broken behaviour.

### Feature Docs Are Authoritative

**CRITICAL**: Feature documentation is the **ground truth** for what a feature should do.

- If a feature document exists, the implementation **MUST** align with it
- If code behaves differently than documented, the code is wrong OR the document must be updated
- Engineers **MUST** keep feature documents accurate - outdated documents are unacceptable
- When implementation changes, update the feature document in the same change

### Describe Behaviour, Not Implementation

Feature documents describe **what** a feature does and **why** it exists at an architectural level. They are
not meant to document implementation internals — instead, they reference source files and let the code speak
for itself.

- Focus on capabilities, behaviour, and integration points
- Use the Implementation section to list source file references, not to explain code logic
- When tempted to describe an algorithm, a data structure, or a signature in detail, add a source file
  reference instead

The dividing line is who the reader is. Someone deciding whether a check will accept their document reads a
feature document; someone changing how that check walks an outline reads the module. A feature document that
transcribes the walk has taken on a second reason to change and will drift from the module on the first
refactor.

### One Document, One Subject

**A feature document has exactly one reason to change.** Split by subject, not by size: a document that
covers both the outline dialect and the budget dialect is rewritten whenever either changes, and neither
change can be reviewed on its own.

Decide a document's home by asking what would force it to be rewritten:

| The document changes when…                | It belongs in…                             |
|-------------------------------------------|--------------------------------------------|
| A spec dialect gains or drops a field     | The document for that dialect              |
| A check's findings change wording or rule | The document for that check                |
| The command surface changes               | The document for that command surface      |
| A corpus's layout changes                 | The document for that corpus               |

Siblings **link**; they do not restate. A behaviour documented twice has two places to rot and no authority
when they disagree.

### Rules Describe What Exists

A feature document describes behaviour that **exists in this repository**, not behaviour that is planned.

- Do not document a flag, a field, or an exit code the toolkit does not have
- Do not carry a "coming soon" section; an unbuilt feature has no document
- If a document claims a capability the code lacks, one of the two is a bug — fix the code or delete the
  claim in the same change

### A Document's Path Selects Its Specifications

Nothing registers a feature document with a specification: the document's own path and `type` resolve them.

A document at `docs/feat/<name>.md` is governed by four files in `docs/__meta__/`:

| File                  | Governs                                    | Read by                                    |
|-----------------------|--------------------------------------------|--------------------------------------------|
| `feat.md`             | Everything. This document is the authority | A person, and an agent before it writes    |
| `feat.header.json`    | Frontmatter fields, vocabularies, patterns | `check_header.py`                          |
| `feat.structure.json` | The section outline and its order          | `check_structure.py`                       |
| `feat.budget.json`    | Prose length, per document and per section | `check_budget.py`                          |

Two kinds of narrowing layer onto that base, and both are additive — a layer states only what it adds, and
none can release a document from what the base already said:

- **A filename prefix layer**, `feat-<prefix>.header.json`, `feat-<prefix>.structure.json` or
  `feat-<prefix>.budget.json`, where `<prefix>` is the filename up to its first hyphen. None exist today;
  add one when a naming group genuinely shares rules the rest of the corpus does not.
- **A type layer**, `feat.<type>.structure.json`, selected by the document's `type` field. All three exist:
  `feat.feature.structure.json`, `feat.component.structure.json` and `feat.meta.structure.json`. This is
  where a per-type section rule lives — never as a condition inside `feat.structure.json`, which asks no
  questions about the document it is applied to ([§4](#4-document-structure)).

The three checks run together as `just check-docs`. Read the relationship in either direction from the shell:

```bash
ls docs/feat/*.md       # from a specification, the documents it governs
ls docs/__meta__/feat*  # from a document, the specifications that govern it
```

**Prose and schema are one rule set in two forms.** When a rule here changes, change the JSON companion in
the same commit, or the corpus starts accepting what this document forbids.

### Discoverability Through Frontmatter

Feature documents use YAML frontmatter for lazy loading - agents query frontmatter to determine which
documents to load based on the question in front of them, rather than reading the corpus up front.

### Avoid Context Bloat

Keep feature documents focused and concise. Agent entrypoint documents should NOT hardcode feature lists -
use dynamic discovery instead. A word written here is paid for on every task that touches the subject, which
is what [§6](#6-prose-budget) puts a number on.

---

## 2. Frontmatter Requirements

The rules in this section are held in machine-checkable form in
[feat.header.json](feat.header.json), which `just check-docs` runs against every document in the corpus.

**CRITICAL**: Every feature document MUST begin with valid YAML frontmatter:

```yaml
---
name: "feature-name-kebab-case"
description: "What it explains + when to load it"
type: "meta|feature|component"
status: "stable|experimental|unstable|development"
components: "prefix:name,prefix:name"
---
```

**All five values are double-quoted**, as the block above writes them. YAML accepts a bare `type: feature`,
so the two forms coexist happily and drift apart silently; one form means a diff on a field is always a
change of value, never a change of style. The schema cannot see quoting — a YAML parse has already discarded
it — so this one is verified by reading.

### Field Requirements

| Field         | Required | Format                            | Description                                                         |
|---------------|----------|-----------------------------------|---------------------------------------------------------------------|
| `name`        | YES      | `^[a-z0-9]+(-[a-z0-9]+)*$`        | Unique identifier matching filename (minus .md)                     |
| `description` | YES      | Single line, succinct             | Discovery-optimized description (see guidelines below)              |
| `type`        | YES      | `meta`, `feature`, or `component` | Document classification (see Type Definitions below)                |
| `status`      | YES      | enum                              | Maturity level: `stable`, `experimental`, `unstable`, `development` |
| `components`  | YES      | Prefixed, comma-separated         | Related modules, skills and specifications, each with a type prefix |

### Type Definitions

| Type | Purpose | Characteristics |
|------|---------|-----------------|
| `meta` | Groups related features/concepts | High-level overview, no Usage section, cannot link to children |
| `feature` | Documents a user-facing capability | What a user can do, requires Usage section with examples |
| `component` | Documents a software component | Internal architecture, requires Implementation section |

**meta documents:**
- Describe a domain or capability group (e.g. `check`, `spec`, `corpus`)
- Provide conceptual foundation and terminology
- MUST NOT link to child documents (children link up to meta)
- MUST NOT carry a Usage or an Implementation section (concrete usage lives in the children)

**feature documents:**
- Describe capabilities a user of this toolkit invokes
- Focus on "what can a user do" and "how do they do it"
- MUST include a Usage section with working examples
- May link to related features, to the components that implement them, and to the parent meta document

**component documents:**
- Describe an internal building block — a module, a subpackage, a spec dialect's reader
- Focus on architecture, responsibilities, and integration
- MUST include an Implementation section with source files
- May link to related components, to features, and to the parent meta document

### Status Definitions

The `status` field indicates the maturity and stability of a feature:

| Status         | Work-in-Progress | Quality                   | Notes                                                                                |
|----------------|------------------|---------------------------|--------------------------------------------------------------------------------------|
| `stable`       | Production Ready | GA (General Availability) | Breaking changes require a deprecation cycle; fully tested and documented            |
| `experimental` | Minor            | Dev Preview               | Functional but the interface may change between releases; suitable for evaluation    |
| `unstable`     | Active           | Alpha                     | Implemented but has sharp edges or incomplete areas; expect significant changes      |
| `development`  | Heavy            | N/A                       | Under active design; details may change or the feature may be removed                |

#### State Progression

Features progress through maturity states:

```
development ─> unstable ─> experimental ─> stable
```

**Progression criteria:**

- **development → unstable**: Core functionality implemented, basic tests pass
- **unstable → experimental**: Interface stabilizing, documentation complete, integration tests pass
- **experimental → stable**: Production testing complete, no breaking changes planned

**Regression**: A feature may regress if a critical bug is found, if significant refactoring is needed, or
if an interface redesign becomes necessary.

`status` is not a release note. It states where the feature stands today; it does not narrate how it got
there, and a version number never appears in it.

### Component Prefixes (MANDATORY)

The `components` field names the things a change to this feature would touch. Every entry MUST carry one of
these three prefixes:

| Prefix    | Names                                                       | Spelling                        | Example                       |
|-----------|-------------------------------------------------------------|---------------------------------|-------------------------------|
| `module:` | A module or subpackage under `src/lorecraft/`              | snake_case, dotted for nesting  | `module:checkers.structure`   |
| `skill:`  | A skill directory under `.agents/skills/`                   | kebab-case                      | `skill:docs-rules-check`      |
| `spec:`   | A specification file stem under `docs/__meta__/`            | kebab-case, dotted for a layer  | `spec:feat.feature`           |

The distribution's top-level package is `lorecraft`, so a `module:` entry never repeats it:
`src/lorecraft/checkers/structure.py` is `module:checkers.structure`, not `module:lorecraft.checkers.structure`.

**Example:**
```yaml
components: "module:checkers.structure,spec:feat,skill:docs-rules-check"
```

The schema enforces the prefix vocabulary and the character set of each entry. Which separator a given prefix
uses — a dot for a module path, a hyphen for a skill directory — is stated in the table above and verified by
reading, because a single regular expression covering all three at once is less readable than the rule it
would encode.

### Description Guidelines

Write descriptions optimized for dynamic discovery. Unlike skills, which are executed, feature documents are
loaded to answer questions and to navigate the repository. Your description must answer two questions:

1. **What does this document explain?** - List the specific capabilities or concepts covered
2. **When should an agent load it?** - Include trigger terms via a "Load when" clause

**Requirements:**
- Written in third person (no "I" or "you")
- Include a "Load when" clause with trigger conditions
- Be specific - avoid vague words like "overview", "various", "handles"
- No ending period

**Examples:**
- ✅ `"Outline matching, the any run, and corpus/prefix/type layering. Load when writing or debugging a structure spec"`
- ✅ `"Word counting rules and the per-section caps a budget sets. Load when a document is reported over budget"`
- ✅ `"Exit codes and the text and JSON finding formats. Load when wiring a check into CI or a pre-commit hook"`
- ❌ `"Overview of the structure checker"` (vague, no trigger)
- ❌ `"Handles various document checks"` (vague, no specifics)

### Discovery Command

The discovery command extracts the frontmatter fields of every feature document for lazy loading:

```bash
grep -m 4 -E '^(description|type|status|components):' docs/feat/*.md
```

---

## 3. Naming Schema

Feature names follow a hierarchical pattern from broad domain to specific feature:

**Pattern:** `<domain>-<subdomain>-<variant>`

The first kebab-case segment is the **domain**, and it is what a prefix layer in `docs/__meta__/` would match
([§1](#1-core-principles)). Files sharing a domain sort together and are found by one glob.

### Examples by Domain

**Check features:**
```
check                             # Meta: what the toolkit checks, and how a document selects its specs
├── check-header                  # Frontmatter against a JSON Schema
├── check-structure               # Section outlines against a structure spec
│   ├── check-structure-outline   # Outline matching and the free-run entry
│   └── check-structure-layers    # Corpus, prefix and type layering
├── check-budget                  # Prose length against a word budget
└── check-skill                   # Skill directories against the Agent Skills specification
```

**Specification features:**
```
spec                              # Meta: the specification files under docs/__meta__/
├── spec-header                   # The JSON Schema dialect
├── spec-structure                # The outline dialect
└── spec-budget                   # The budget dialect
```

**Corpus features:**
```
corpus                            # Meta: what makes a directory under docs/ a governed corpus
├── corpus-code                   # The rule corpus and its prefix groups
└── corpus-feat                   # The feature corpus and its type layers
```

**Command features:**
```
cli                               # Meta: the command surface the toolkit exposes
├── cli-selection                 # Path arguments, corpus discovery, repository root resolution
└── cli-output                    # Text and JSON finding formats, and exit codes
```

### Naming Rules

1. **Use kebab-case** - All lowercase, words separated by hyphens
2. **Domain first** - Start with the broad capability area
3. **Progressively specific** - Add specificity with each segment
4. **Match filename** - The `name` field must match the filename (minus .md)
5. **Alphabetical grouping** - Related features sort together
6. **Flat directory** - Every document lives at the root of `docs/feat/`; the hierarchy is in the name, not
   in subdirectories, because the specification layers resolve on the filename

### Benefits

- **Discoverable** - Searching "check" finds every check feature
- **Hierarchical** - A child document references its parent meta document for shared context
- **Scalable** - A new feature slots into the existing hierarchy without moving anything
- **Organized** - Natural grouping when listing files

---

## 4. Document Structure

The rules in this section are held in machine-checkable form in
[feat.structure.json](feat.structure.json) and the three type layers beside it
([§1](#1-core-principles)).

### Required Sections by Type

Different document types have different required sections:

| Section | meta | feature | component |
|---------|:----:|:-------:|:---------:|
| H1 Title | ✓ | ✓ | ✓ |
| Summary | ✓ | ✓ | ✓ |
| Table of Contents | ✓ | ✓ | ✓ |
| Key Concepts | ✓ | ✓ | ✓ |
| Architecture | optional | optional | optional |
| Configuration | optional | optional | optional |
| Usage | ✗ | ✓ | optional |
| Implementation | ✗ | optional | ✓ |
| Limitations | optional | optional | optional |
| References | optional | optional | optional |

**Section descriptions:**

1. **H1 Title** - Human-readable feature name, and the only H1 in the document
2. **Summary** - 2-4 sentences expanding on the frontmatter description
3. **Table of Contents** - Links to the sections below it
4. **Key Concepts** - The terms this document uses, defined once
5. **Architecture** - How the feature fits together: data flow, component interaction
6. **Configuration** - Options, defaults, and where they are read from
7. **Usage** - How to invoke the feature, with examples that run
8. **Implementation** - File locations and internal notes, not code logic
9. **Limitations** - Known constraints
10. **References** - Cross-references to other feature documents

### Section Order

**The order in the table above is the order on the page.** Summary, Table of Contents and Key Concepts open
every document, in that order; References closes it, and nothing follows References. The optional sections
between them keep their relative order whether or not each is present, so two documents that carry different
subsets still read the same way.

A document may add a section of its own — a dialect's field reference, a findings table — and those go after
the named sections and before References. A section written out of that order is reported against this
section, by name.

### Optional Sections

**CRITICAL**: No empty sections allowed. If you include a section header, it must have content. Omit optional
sections entirely rather than leaving them empty. A required section is not satisfied by a bare heading.

### References Section Format

Use a simple list, with the relationship named before the description:

```markdown
## References

- [check-structure](check-structure.md) - Dependency: outline matching
- [spec-structure](spec-structure.md) - Related: the dialect this check reads
- [check](check.md) - Base: the check family this belongs to
```

**Relationship types:** `Dependency`, `Alternative`, `Related`, `Extended by`, `Base`

### Reference Direction Rules

Reference rules depend on document type:

| From Type   | Can Link To                                                  |
|-------------|--------------------------------------------------------------|
| `meta`      | Other meta documents only (siblings at the same level)       |
| `feature`   | Parent meta, sibling features, related components            |
| `component` | Parent meta, related features, child components              |

**Key principles:**
- ✅ **meta** documents MUST NOT link to children (features and components link UP to meta)
- ✅ **component** documents MAY link to child components they contain
- ✅ **feature** and **component** documents link UP to their parent meta document

**This rule applies to:**
- The References section
- Inline links in prose
- Links in Architecture diagrams or tables
- Any markdown link `[text](file.md)` pointing to a feature document

**Rationale**: Meta documents provide stable, high-level context. Linking downward creates a maintenance
burden whenever a child is added, removed or renamed; it couples a stable document to volatile detail; and
it invites circular references between documents.

**Examples:**
- ✅ `check-structure.md` (component) → `check.md` (meta) — child to parent
- ✅ `check-structure.md` (component) → `spec-structure.md` (feature) — component to the feature it serves
- ✅ `cli-output.md` (feature) → `cli.md` (meta) — feature to parent meta
- ❌ `check.md` (meta) → `check-structure.md` (component) — FORBIDDEN: meta to child
- ❌ `spec.md` (meta) → lists `spec-budget.md` (feature) — FORBIDDEN: meta to child

Direction is a judgment the checker does not make. It is on the author, and on review.

---

## 5. Content Guidelines

### DO

- Keep descriptions focused and actionable
- Reference specific modules and files with paths, in the Implementation section
- Include examples that run, in fenced blocks
- Use the terminology defined in Key Concepts, and define each term once
- Show the command a reader would actually type
- State the exit code and the finding format where a reader needs to script against it

### DON'T

- Duplicate content from `docs/code/` (link instead)
- Explain code logic; name the source file and let the code speak
- Restate a sibling's behaviour (link instead)
- Hardcode paths that change frequently
- Add speculative or planned features
- Narrate a migration, or argue the case for a decision already made
- Record dependency versions, release status, or benchmark figures
- Use vague descriptions ("various", "multiple", "etc.")
- Leave an optional section empty (omit it instead)

---

## 6. Prose Budget

A feature document is loaded into an agent's context on demand, so every word in it is paid for on every task
that touches its subject. The caps in [feat.budget.json](feat.budget.json) put a number on that, and
`just check-docs` reports what is over.

| Scope                                    | Words |
|------------------------------------------|------:|
| The whole document, frontmatter excluded |  1200 |
| Summary                                  |    80 |
| Key Concepts                             |   200 |
| Architecture                             |   400 |
| Usage                                    |   400 |
| Implementation                           |   150 |
| Limitations                              |   200 |
| Any other section                        |   300 |

**A word is whitespace-delimited text outside fenced code blocks and outside table rows.** Code and tables
are free: they are the examples and the reference material a feature document exists to hold, and charging
for them would push an author toward prose where a table is clearer.

Table of Contents and References carry no section cap — both are lists of links whose length is a function of
the document, not a choice — but their words still count toward the document total.

A section over budget is a signal about structure, not an invitation to compress. Split the subject into two
documents ([§1](#1-core-principles)), move the detail into the module it describes, or replace a paragraph
with the table it was describing.

---

## 7. Template

Use this template when creating a new feature document:

````markdown
---
name: "{{feature-name-kebab-case}}"
description: "{{What it explains + Load when [trigger conditions], third person, no period}}"
type: "{{meta|feature|component}}"
status: "{{stable|experimental|unstable|development}}"
components: "{{prefix:name,prefix:name - use module:, skill:, or spec:}}"
---

# {{Feature Title - Human Readable}}

## Summary

{{2-4 sentences providing more context than the frontmatter description.
What this feature does, why it exists, and its primary use.}}

## Table of Contents

1. [Key Concepts](#key-concepts)
2. [Architecture](#architecture) {{if the flow is not obvious from usage}}
3. [Configuration](#configuration) {{if applicable}}
4. [Usage](#usage) {{REQUIRED for feature, optional for component, forbidden for meta}}
5. [Implementation](#implementation) {{REQUIRED for component, optional for feature, forbidden for meta}}
6. [Limitations](#limitations) {{if applicable}}
7. [References](#references) {{if cross-referencing - follow the direction rules}}

## Key Concepts

{{Define the 3-5 terms this document uses throughout:}}

- **Term**: What this term means here, in one line
- **Term**: What this term means here, in one line

## Architecture {{OPTIONAL}}

{{How the pieces fit together. Include this section when the feature has a flow worth
naming or an interaction that usage examples do not show. Omit it when usage is
self-explanatory.}}

### Resolution Flow {{or Data Flow, Component Interaction, etc.}}

1. Step one of the flow
2. Step two of the flow
3. Step three of the flow

## Configuration {{OPTIONAL}}

| Setting | Default | Description |
|---------|---------|-------------|
| option_name | default_value | What this option controls |

## Usage

### Basic Usage

```bash
{{The command a reader types, and what it prints}}
```

### Advanced Usage {{if applicable}}

```bash
{{A second example that shows something the first does not}}
```

## Implementation {{OPTIONAL}}

{{File locations and internal notes. Name files; do not explain their logic.}}

### Source Files

- `src/lorecraft/{{path/to/module.py}}` - How this file relates to the feature

## Limitations {{OPTIONAL}}

- Limitation one
- Limitation two

## References {{OPTIONAL}}

- [feature-name](feature-name.md) - Relationship: Brief description
- [another-feature](another-feature.md) - Relationship: Brief description
````

---

## 8. Checklist

Before committing a feature document:

### Frontmatter

- [ ] Valid YAML frontmatter with opening and closing `---`
- [ ] All five values are double-quoted
- [ ] `name` is kebab-case and matches the filename (minus .md)
- [ ] `type` is one of: `meta`, `feature`, `component`
- [ ] `status` is one of: `stable`, `experimental`, `unstable`, `development`
- [ ] `status` reflects where the feature stands today, and names no version
- [ ] `description` says what it covers and includes a "Load when" clause (no ending period)
- [ ] `components` entries all use `module:`, `skill:` or `spec:`, spelled as [§2](#2-frontmatter-requirements) requires
- [ ] No `module:` entry repeats the `lorecraft` top-level package

### Structure

- [ ] One H1 title, human readable, before any section
- [ ] Summary (2-4 sentences), then Table of Contents, then Key Concepts
- [ ] **If type=feature**: a Usage section with examples that run (REQUIRED)
- [ ] **If type=component**: an Implementation section naming source files (REQUIRED)
- [ ] **If type=meta**: no Usage and no Implementation section
- [ ] Optional sections appear in the order [§4](#4-document-structure) fixes
- [ ] Any section the document invents sits after the named sections and before References
- [ ] References, if present, is the last section
- [ ] No empty sections (omit an optional section rather than leaving it empty)

### Cross-References

- [ ] References use the defined relationship types (`Dependency`, `Alternative`, `Related`, `Extended by`, `Base`)
- [ ] **meta** documents do NOT link to children, in the References section or inline
- [ ] **feature** documents link UP to the parent meta, and MAY link to related components
- [ ] **component** documents link UP to the parent meta, and MAY link to child components

### Content

- [ ] Every behaviour documented exists in this repository today
- [ ] The document describes behaviour, not code logic; internals are a file reference
- [ ] The document has one subject — a single reason to change
- [ ] No behaviour is restated from a sibling or from `docs/code/` (linked instead)
- [ ] Examples are accurate, and every command shown is one the repository has
- [ ] No dependency version, release status, benchmark figure, or migration narrative appears
- [ ] Terminology matches the Key Concepts section

### Budget

- [ ] The document is within the totals in [§6](#6-prose-budget)
- [ ] A section that ran over was split or moved, not compressed into unreadable prose

### Discovery

- [ ] The description is optimized for agent discovery
- [ ] The document is found by the discovery command in [§2](#2-frontmatter-requirements)
- [ ] Trigger conditions are clear and specific

### Review

Run `just check-docs` before committing, and read this checklist against the document by hand: the checks
cover frontmatter, section outline and length, and nothing else. Reference direction, whether a Summary
actually summarizes, and whether a document has one subject are judgment calls that stay with the author and
the reviewer.
