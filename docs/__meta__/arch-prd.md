---
name: "arch-prd"
description: "Structure template for `docs/arch/prd-*.md` product requirements documents, one per feature, each stating what the feature must do, for whom and why, before it is built. Load when writing or reviewing a PRD in docs/arch/"
type: "meta"
scope: "global"
---

# Product Requirements Document Meta Spec

**Applies to every document in `docs/arch/` named `prd-*.md`.** The namespace also matches a bare `prd.md`, and
no such file may exist: every PRD is about one feature, and its name says which. It is a namespace layer on the
[arch](arch.md) corpus meta spec, and states only what it adds to it. Its machine-checkable half is
[arch-prd.structure.json](arch-prd.structure.json), applied on its own beside the corpus file.

A PRD states **what** a feature must do and **why**, and nothing about **how**. Its reader is an agent or a
person who will build the feature without a follow-up conversation, so every requirement is explicit, numbered
and checkable. How the feature is built goes in a design document, and each decision taken while building it
goes in a decision record. What shipped goes in the feat spec. The PRD links them all.

## 1. Naming

A PRD is named `prd-<NNN>-<feature>.md`, as in `prd-007-structured-checks.md`:

- **`<NNN>`** is the document number the [arch](arch.md#2-naming) corpus allocates: one sequence shared by every
  document in `docs/arch/`, so no PRD shares its number with any other document, an ADR included.
- **`<feature>`** names the feature in a few kebab-case words. It is for a reader scanning the directory; the
  number alone identifies the PRD, and `prd-007` is how other documents cite it.

## 2. Frontmatter

| Field | Value | Notes |
|---|---|---|
| `name` | `prd-<NNN>-<feature>` | Matches the filename minus `.md`; see [Naming](#1-naming) |
| `description` | One sentence | The feature, and the problem it solves |
| `type` | `"prd"` | Always |
| `status` | `draft`, `approved`, `shipped` or `dropped` | `approved` once no open question is left; frozen once `shipped` or `dropped` |

## 3. Sections

| Section | Required | Holds |
|---|---|---|
| Problem | yes | The need, who has it, and why now |
| Goals | yes | The outcomes the feature commits to |
| Non-Goals | yes | What is explicitly out of scope |
| User Stories | yes | Prioritised stories, each testable on its own, each with Gherkin scenarios |
| Requirements | yes | Numbered `FR-` and `NFR-` items, one behaviour each, in EARS form |
| Edge Cases | no | Boundary conditions and failure paths the stories do not cover |
| Key Entities | no | The concepts the requirements name, without their representation |
| Success Criteria | yes | Numbered `SC-` items, measurable and technology-agnostic |
| Assumptions | no | What the requirements take for granted |
| Open Questions | no | Every `[NEEDS CLARIFICATION]` marker, gathered |
| References | yes | The issue it comes from, and the documents it leads to |

The sections are the whole document, in this order; a PRD adds none of its own. No section has a word cap and the
file has no token budget, as the `arch` corpus states for every document in it: a PRD is as long as its
requirements need. Problem, Goals and Non-Goals still state a few outcomes each, and the requirements carry the
detail.

**No implementation.** A PRD names no language, library, package, module, file format or algorithm. If a
requirement cannot be stated without one, the requirement is a design decision.

## 4. User Stories

A user story is one journey through the feature, told from the user's side. Each one is an H3 that opens with
its identifier, `US-1`, `US-2` and on, gives a short title, and ends with its priority. Identifiers are stable
and never reused, as requirement identifiers are. Under the heading, a story holds three parts:

- **The story:** "As a {{user}}, I want {{capability}}, so that {{benefit}}." The user is a role, not a person.
  The benefit says why the capability matters, not what it does again.
- **The independent test:** how the story is verified with no other story built. A story that cannot be tested
  alone is part of another one, and is merged into it.
- **The acceptance:** one or more scenarios, each in a `gherkin` block of its own, holding one `Scenario:` with
  its `Given`, `When` and `Then` steps, and `And` or `But` to extend one. The `Then` is something the user
  observes, not something inside the system.

**Scenarios specify; they do not run.** A block holds no `Feature:` line, since the H3 already names the story,
and its steps describe the user's world rather than the system's internals, even though Gherkin is built to be
executed. One scenario per block keeps each one quotable and diffable on its own.

**Priority orders delivery.** `P1` is the smallest slice worth shipping on its own; each later priority builds
on the ones before it. Two stories may share a priority.

For example:

````markdown
### US-1: See what is unchecked (P1)

As a writer adopting Lorecraft, I want every ungoverned document reported, so that I know which ones no check
reads.

**Independent test:** Check a workspace that holds documents and no meta spec.

```gherkin
Scenario: No corpus has a meta spec
  Given a workspace with no meta spec
  When the writer checks it
  Then every document is reported as unvalidated
```

```gherkin
Scenario: One corpus has a meta spec
  Given a workspace where only the code corpus has a meta spec
  When the writer checks it
  Then only the documents outside the code corpus are reported as unvalidated
```
````

A story that names the implementation, or whose outcome the user cannot see, is rewritten from the user's side:

````markdown
<!-- ❌ Bad — names the implementation, has no benefit, and its outcome is internal -->
As a developer, I want the loader to cache parsed meta specs.

```gherkin
Scenario: A meta spec is read twice
  Given a loaded meta spec
  When it is read again
  Then the cache is hit
```

<!-- ✅ Good — the user's role, what they gain, and an outcome they observe -->
As a writer, I want a check of a large workspace to finish quickly, so that I can run it on every save.

```gherkin
Scenario: A large workspace
  Given a workspace of 1,000 documents
  When the writer checks it
  Then the result is printed in under two seconds
```
````

## 5. Requirements

A requirement is one observable behaviour, stated so that a test can pass or fail against it. Each one is a list
item that opens with its identifier: `FR-` for a functional requirement, which is what the system does, and
`NFR-` for a non-functional one, which is how well it does it. The two series are numbered separately, from `001`.

**Identifiers are stable.** `FR-003` keeps its number when `FR-002` is removed, and a removed number is never
reused, so that design documents, decision records, tests and feat specs can cite a requirement by its
identifier.

**One pattern per requirement.** Each requirement follows one of the EARS (Easy Approach to Requirements
Syntax) patterns, and the keyword that opens it says when it applies:

| Pattern | Form | Applies |
|---|---|---|
| Ubiquitous | THE SYSTEM SHALL … | Always |
| Event-driven | WHEN … THE SYSTEM SHALL … | When a trigger occurs |
| State-driven | WHILE … THE SYSTEM SHALL … | For as long as a state holds |
| Unwanted behaviour | IF … THEN THE SYSTEM SHALL … | When something goes wrong |
| Optional feature | WHERE … THE SYSTEM SHALL … | Only where a feature or option is present |

For example:

- **FR-001:** THE SYSTEM SHALL report every finding with the path of the document it was found in.
- **FR-002:** WHEN a user checks a workspace that holds no meta spec, THE SYSTEM SHALL report every document
  as unvalidated.
- **FR-003:** WHILE any meta spec cannot be loaded, THE SYSTEM SHALL check no document.
- **FR-004:** IF a document's frontmatter cannot be parsed, THEN THE SYSTEM SHALL report one finding for it and
  go on to the next document.
- **FR-005:** WHERE the user asks for machine-readable output, THE SYSTEM SHALL write each finding as one record.
- **NFR-001:** THE SYSTEM SHALL check a workspace of 1,000 documents in under two seconds.

A requirement that bundles several behaviours, or that cannot fail, is split or sharpened until each part can:

```markdown
<!-- ❌ Bad — two behaviours, and "fast" and "gracefully" cannot fail a test -->
- **FR-001:** The check should be fast and handle broken documents gracefully.

<!-- ✅ Good — one behaviour each, each with an outcome a test observes -->
- **FR-001:** IF a document cannot be parsed, THEN THE SYSTEM SHALL report one finding for it and go on to the
  next document.
- **NFR-001:** THE SYSTEM SHALL check a workspace of 1,000 documents in under two seconds.
```

**Unknowns are marked, not guessed.** A requirement the writer cannot yet state in full carries an inline
`[NEEDS CLARIFICATION: <the question>]` and is listed under Open Questions:

- **FR-006:** WHEN a document is renamed, THE SYSTEM SHALL report its old path [NEEDS CLARIFICATION: in every
  output format, or in the text output only?].

## 6. Template

````markdown
---
name: "prd-{{NNN}}-{{feature}}"
description: "{{The feature, and the problem it solves, in one sentence}}"
type: "prd"
status: "draft"
---

# {{Feature Name}}

## Problem

{{Who needs this, what they cannot do today, and why it matters now. One or two paragraphs.}}

## Goals

- {{An outcome the feature commits to}}

## Non-Goals

- {{Something a reader might expect that this feature does not do, and why}}

## User Stories

### US-1: {{Short title}} (P1)

As a {{user}}, I want {{capability}}, so that {{benefit}}.

**Independent test:** {{How this story is verified on its own, with no other story built}}.

```gherkin
Scenario: {{Short title}}
  Given {{initial state}}
  When {{action}}
  Then {{observable outcome}}
```

### US-2: {{Short title}} (P2)

{{…}}

## Requirements

- **FR-001:** WHEN {{trigger}} THE SYSTEM SHALL {{behaviour}}.
- **FR-002:** WHILE {{state}} THE SYSTEM SHALL {{behaviour}}.
- **FR-003:** IF {{unwanted condition}} THEN THE SYSTEM SHALL {{response}}.
- **FR-004:** WHERE {{feature or option}} THE SYSTEM SHALL {{behaviour}}.
- **FR-005:** THE SYSTEM SHALL {{behaviour}} [NEEDS CLARIFICATION: {{the question}}].
- **NFR-001:** THE SYSTEM SHALL {{quality: performance, compatibility, limits}}.

## Edge Cases {{OPTIONAL}}

- What happens when {{boundary condition}}?

## Key Entities {{OPTIONAL}}

- **{{Entity}}:** {{What it is to the user, and how it relates to the others}}.

## Success Criteria

- **SC-001:** {{A measurable outcome, stated without naming the technology}}.

## Assumptions {{OPTIONAL}}

- {{Something the requirements take for granted}}

## Open Questions {{OPTIONAL}}

- **FR-005:** {{The question}}

## References

- [#{{issue}}]({{issue-url}}) - Source: {{The issue the PRD comes from}}
- [{{design-document}}]({{design-document}}.md) - Leads to: {{How the feature is built}}
- [{{feat-spec}}](../feat/{{feat-spec}}.md) - Leads to: {{What shipped}}
````

## 7. Checklist

- [ ] The file is named `prd-<NNN>-<feature>.md`, `name` matches it, and `status` is one of the four values
- [ ] The number is the next free one in `docs/arch/`, and no other document, merged or dropped, has it
- [ ] No section names a language, library, package, module, file format or algorithm
- [ ] Every non-goal says why it is out of scope
- [ ] Every user story has a priority, an independent test, and at least one scenario
- [ ] Every scenario is a `gherkin` block of its own, with one `Scenario:` and no `Feature:`, and a `Then` the
  user observes
- [ ] Every requirement has an identifier, states one behaviour in EARS form, and can be verified
- [ ] No identifier was renumbered or reused
- [ ] Every success criterion is measurable
- [ ] Every `[NEEDS CLARIFICATION]` marker is listed under Open Questions, and an `approved` PRD has none
- [ ] A `shipped` PRD links the feat spec it led to
