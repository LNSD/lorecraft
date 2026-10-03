---
name: "arch-adr"
description: "Format of `docs/arch/adr-*.md` architecture decision records: how a feature or a part of the system is built, and why, with the few sections every decision needs and room for any other. Load when writing or reviewing an ADR in docs/arch/"
type: "meta"
scope: "global"
---

# Architecture Decision Record Specification

**Applies to every document in `docs/arch/` named `adr-*.md`.** The namespace also matches a bare `adr.md`, and no
such file may exist: every ADR is about one decision, and its name says which. It is a namespace layer on the
[arch](arch.md) corpus specification, and states only what it adds to it. Its machine-checkable half is
[arch-adr.structure.json](arch-adr.structure.json), applied on its own beside the corpus file.

An ADR states **how** something is built and **why**: the context that forced a decision, the decision, and what
follows from it. It answers a PRD's requirements when there is one, and cites them by identifier. It is
deliberately flexible: a short record of one choice and a full design document are both ADRs, and the sections
beyond the three below are the writer's.

## 1. Naming

An ADR is named `adr-<NNN>-<subject>.md`, as in `adr-004-database.md`. `<NNN>` is the document number the
[arch](arch.md#2-naming) corpus allocates, shared with every other document in `docs/arch/`, so an ADR never shares
its number with the PRD it answers. `adr-<NNN>` is how other documents cite it.

## 2. Frontmatter

| Field | Value | Notes |
|---|---|---|
| `type` | `"adr"` | Always |
| `status` | `proposed`, `accepted`, `rejected`, `superseded` or `deprecated` | `accepted` once the owner settles it; frozen once `rejected`, `superseded` or `deprecated` |

A `superseded` ADR names the ADR that replaces it under References, and that ADR names it back.

**An accepted ADR binds code.** It is a rule like any in `docs/code/`: agents load it by its `description`, so the
description ends with a trigger clause, `Load when …`, naming the work it governs, and a `## Checklist` of
`- [ ]` items, one per verifiable statement, is what a code review walks. A `proposed`, `rejected`,
`superseded` or `deprecated` ADR binds nothing.

## 3. Sections

| Section | Required | Holds |
|---|---|---|
| Context | yes | The situation and the forces that call for a decision |
| Decision | yes | What is decided, as statements a reader can hold the result to |
| Consequences | yes | What follows: what changes, what it costs, and what stays true |

The three appear in this order. Any other section may sit before, between or after them, such as a glossary, a
design, the alternatives considered, what is deferred, or the questions still open; and References closes the
document, as the corpus states. No section has a word cap and the file has no token budget.

An ADR may name languages, libraries, modules and types: how a thing is built is what it records.

## 4. Template

````markdown
---
name: "adr-{{NNN}}-{{subject}}"
description: "{{What is decided, in one sentence}}"
type: "adr"
status: "proposed"
---

# {{Subject}}

## Context

{{The situation, and the forces that call for a decision.}}

## Decision

1. **{{A decision}}.** {{What it means.}}

## Consequences

- {{What changes, what it costs, what stays true.}}

## References

- [prd-{{NNN}}](prd-{{NNN}}-{{feature}}.md) - Source: {{The requirements this decision answers}}
````

## 5. Checklist

- [ ] The file is named `adr-<NNN>-<subject>.md`, and `status` is one of the five values
- [ ] Context, Decision and Consequences appear, in that order
- [ ] Each decision is stated so that the result can be held to it
- [ ] A requirement the ADR answers is cited by its identifier
- [ ] A `superseded` ADR names its replacement, and the replacement names it back
- [ ] An `accepted` ADR's description ends with a `Load when …` trigger, and it carries a checklist when it
  states something code can be checked against
