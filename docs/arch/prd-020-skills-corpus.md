---
name: "prd-020-skills-corpus"
description: "A reserved skills corpus in the spec directory that governs every agent skill's entrypoint by the skill's name, layered on the Agent Skills specification, so a repository can state its own rules for its skills as it does for its documents"
type: "prd"
status: "approved"
---

# Skills Corpus

## Problem

A repository that keeps agent skills beside its documents can state rules for its documents and cannot state
rules for its skills. Under `docs/`, a spec says what every document in a corpus, or in a group of it, must
hold: its frontmatter, its sections, its word caps and its token budget, and `lorecraft check` holds each
document to them. A skill's `SKILL.md` is held to the Agent Skills specification and to nothing else. Those rules
are built in: a maintainer cannot read them as a schema, cannot add to them, and cannot say that every `code-*`
skill carries a section, that the `feat-*` skills stay under a budget, or that every skill sets a frontmatter field
the repository's workflow reads.

Skills are the one kind of governed file that stands outside the model every corpus shares. Bringing them into it
lets a repository write rules for its skills the way it writes them for its documents, and checks both in one run.

## Goals

- One reserved corpus, `skills`, whose spec governs the `SKILL.md` of every skill in `.agents/skills/` by
  the skill's name, with no directory under `docs/` to hold them.
- Namespace specs, `skills-<namespace>`, that govern the skills named `<namespace>` or `<namespace>-*`, and
  layer on the corpus spec and on each other as every namespace spec does.
- The Agent Skills specification's rules published as a built-in skills schema, generated as documentation, that
  the `skills` corpus extends by default for skills.
- A repository that opts out of the built-in schema governs its skills by its own `skills` spec alone.
- One `lorecraft check` run applies both, and `lorecraft inspect` shows which specs govern a skill.

## Non-Goals

- **The Markdown resources inside a skill.** Only `SKILL.md` is governed. Which other files a skill holds are
  checked, and by what, is its own question, explored apart from this feature.
- **The `skills/` directory.** Only the skills in `.agents/skills/` are governed for now, which is where this
  repository's agents read them; whether `skills/` is governed too is left for later.
- **A `docs/skills/` directory.** The corpus is reserved by name; its documents are the skills, wherever the
  agents read them, and no directory under `docs/` is created or read for it; one that exists is reported and
  ignored.
- **Changes to the Agent Skills specification.** The built-in schema states it as it is.
- **Complete compatibility analysis.** Contradiction detection covers the explicit required-field constraints
  listed in FR-008; arbitrary combinations of rules are still enforced against skills, without a promise to
  identify every impossible spec in advance.
- **New kinds of check.** A skills spec carries the same keys any spec does; a check a document cannot
  have, a skill cannot have either.
- **How corpora under `docs/` are matched.** They match as they do today.

## User Stories

### US-1: Rules for every skill (P1)

As a maintainer of a repository's skills, I want to state rules that every skill must follow, so that each new
skill is held to the repository's conventions without a reviewer remembering them.

**Independent test:** Add a `skills` spec that requires a `metadata.<field>` frontmatter field, and check a
workspace with one skill that sets it and one that does not; or check a workspace that opts out of the built-in
schema with a skill requiring a top-level field.

```gherkin
Scenario: A skill breaks a rule of the skills corpus
  Given a skills spec that requires every skill to set a metadata field
  And a skill that does not set it
  When the maintainer checks the workspace
  Then a finding names that skill and the missing field
```

```gherkin
Scenario: A compliant skill satisfies both layers under metadata
  Given a skills spec that requires metadata.owner
  And a skill that sets metadata.owner
  When the maintainer checks the workspace
  Then no finding names that skill
```

```gherkin
Scenario: Top-level repository fields require opting out of the built-in schema
  Given a skills spec that requires a top-level field not defined by Agent Skills
  And a workspace that opts out of the built-in skills schema with --no-agent-skills-spec
  And a skill that sets that top-level field
  When the maintainer checks the workspace
  Then no finding names that skill
```

```gherkin
Scenario: No skills spec
  Given a workspace with skills and no skills spec
  When the maintainer checks the workspace
  Then each skill is held to the Agent Skills specification alone, as before
```

### US-2: Rules for a group of skills (P1)

As a maintainer, I want to state rules for the skills that share a name prefix, so that a group such as the
`code-*` skills carries what the rest do not need.

**Independent test:** Add a `skills-code` spec that requires a section, and check one `code-*` skill and one
`feat-*` skill, neither of which has it.

```gherkin
Scenario: A namespace governs only its skills
  Given a skills-code spec that requires a section
  And the skills code-rules and feat-status, neither with that section
  When the maintainer checks the workspace
  Then a finding names code-rules
  And no finding names feat-status for that section
```

```gherkin
Scenario: Namespaces layer
  Given a skills spec and a skills-code spec
  And a skill named code-rules-check
  When the maintainer checks the workspace
  Then the skill is held to the rules of both specs
```

### US-3: The specification is the floor (P1)

As a maintainer, I want my skills rules to add to the Agent Skills specification and never weaken it, so that a
skill that passes the check still loads in every agent.

**Independent test:** Write a skills spec that requires a non-text description, and check the workspace
without any skills.

```gherkin
Scenario: A skills spec contradicts the specification
  Given a skills spec that requires a non-text description
  And a workspace with no skills
  When the maintainer checks the workspace
  Then the check fails with a finding that names the skills spec and the contradicted rule
```

```gherkin
Scenario: An extension does not repeat a built-in requirement
  Given a skills spec that adds a description constraint without repeating that description is required
  And a skill that omits its description
  When the maintainer checks the workspace
  Then a finding names the skill for its missing description
  And no contradiction finding names the spec for the omitted requirement
```

### US-4: Opting out of the built-in schema (P3)

As a maintainer who does not want the built-in rules, I want to govern my skills by my own schema alone, so
that I can still check them against the rules I choose.

**Independent test:** Opt out of the built-in schema, and check a skill that breaks only a built-in rule.

```gherkin
Scenario: The built-in schema is switched off
  Given a workspace that opts out of the built-in skills schema
  And a skill that breaks a built-in rule and none of the skills spec's rules
  When the maintainer checks the workspace
  Then no finding names that skill
```

```gherkin
Scenario: Opting out of skills governance
  Given a workspace that opts out of the built-in skills schema
  And no skills spec
  When the maintainer checks the workspace
  Then each skill is reported as ungoverned
  And the check reports no error
```

### US-5: What governs a skill (P2)

As a maintainer, I want to see which specs govern a skill, so that I know where a finding's rule comes from.

**Independent test:** Inspect a workspace with a `skills` and a `skills-code` spec.

```gherkin
Scenario: Inspecting a skill
  Given a skills spec and a skills-code spec
  When the maintainer inspects the workspace
  Then the skill code-rules is shown governed by skills and skills-code, broad to narrow
```

### US-6: The built-in rules as a schema (P2)

As a maintainer writing a skills spec, I want to read the rules my skills already follow, so that I extend
them rather than restate them.

**Independent test:** Open the generated documentation for the built-in skills schema.

```gherkin
Scenario: Reading the built-in schema
  Given the published documentation
  When the maintainer looks up the built-in skills schema
  Then every frontmatter rule the check applies to a skill is listed there
```

### US-7: A docs directory with a reserved name (P3)

As a writer, I want to be told when a directory under `docs/` takes a reserved corpus name, so that I know why
its documents are not checked.

**Independent test:** Add a `docs/skills/` directory with one document beside a `skills` spec, and check
the workspace.

```gherkin
Scenario: A docs corpus overlaps the reserved skills corpus
  Given a skills spec
  And a docs/skills/ directory holding a document
  When the writer checks the workspace
  Then a warning names docs/skills/ as overlapping the reserved skills corpus
  And no finding names the document inside it
```

```gherkin
Scenario: The overlap is configured as an error
  Given a workspace that configures the overlap report as an error
  And a docs/skills/ directory beside a skills spec
  When the writer checks the workspace
  Then the check fails with an error that names docs/skills/
```

## Requirements

- **FR-001:** THE SYSTEM SHALL treat `skills` as a reserved corpus name whose documents are the `SKILL.md` of
  every skill in `.agents/skills/`, not documents under `docs/skills/`.
- **FR-002:** WHERE a `skills` spec exists, THE SYSTEM SHALL hold every skill's `SKILL.md` to it.
- **FR-003:** WHERE a `skills-<namespace>` spec exists, THE SYSTEM SHALL hold to it every skill whose name
  equals `<namespace>` or continues it with a hyphen.
- **FR-004:** THE SYSTEM SHALL apply the specs that govern a skill by conjunction, broad to narrow, as it does
  for a document under `docs/`.
- **FR-005:** THE SYSTEM SHALL apply to a skill every kind of check a spec can carry for a document: its
  frontmatter schema, its section outline, its word caps and its token budget.
- **FR-006:** THE SYSTEM SHALL hold every skill to a built-in skills schema that states the Agent Skills
  specification's rules.
- **FR-007:** WHILE the built-in skills schema is in force, THE SYSTEM SHALL apply the `skills` spec as an
  extension of it.
- **FR-008:** WHILE the built-in skills schema is in force, THE SYSTEM SHALL report a finding naming a skills
  spec and the contradicted built-in rule when that spec directly forbids either required field
  (`name` or `description`), excludes text for it, gives it an impossible length range against the built-in
  bounds, or limits it to finite values none of which meets the built-in field rules and the direct type and
  length constraints.
- **FR-009:** WHERE a workspace opts out of the built-in skills schema, THE SYSTEM SHALL hold its skills to its
  skills specs alone.
- **FR-010:** WHEN a user checks a workspace, THE SYSTEM SHALL check its skills and its documents in the same run.
- **FR-011:** WHEN a user inspects a workspace, THE SYSTEM SHALL show, for each skill, the specs that govern
  it, broad to narrow.
- **FR-012:** THE SYSTEM SHALL publish the built-in skills schema as generated documentation.
- **FR-013:** WHERE no skills spec exists and the built-in schema is in force, THE SYSTEM SHALL report on
  every skill exactly the findings it reports today.
- **FR-014:** THE SYSTEM SHALL read no file inside a skill other than its `SKILL.md` for this corpus.
- **FR-015:** IF a corpus under `docs/` has the name of a reserved corpus, THEN THE SYSTEM SHALL report that it
  overlaps the reserved corpus, as a warning unless the workspace configures the report as an error.
- **FR-016:** WHILE a corpus under `docs/` overlaps a reserved corpus, THE SYSTEM SHALL check none of its documents.
- **FR-017:** WHERE a workspace configures the overlap report as an error, THE SYSTEM SHALL fail the check when a
  corpus under `docs/` overlaps a reserved corpus.
- **FR-018:** WHERE a workspace opts out of the built-in skills schema and has no skills spec, THE SYSTEM
  SHALL report its skills as ungoverned, as it reports a document no spec governs, and report no error.
- **FR-019:** IF a contradiction described by FR-008 is found, THEN THE SYSTEM SHALL fail the check.
- **FR-020:** THE SYSTEM SHALL allow a skills spec to omit constraints that the built-in schema enforces
  independently.
- **NFR-001:** THE SYSTEM SHALL name each skills spec, and each finding against a skill, with the same
  vocabulary of corpus, namespace and facet it uses for documents.

## Edge Cases

- A `docs/skills/` directory exists. It is reported as overlapping the reserved corpus and ignored (FR-015,
  FR-016).
- A `skills-<namespace>` spec matches no skill. It still loads and must be valid, as any namespace spec
  that matches no document.
- A skill's name and a longer namespace both match, as `code-rules-check` under `skills-code` and
  `skills-code-rules`. Both govern it, the shorter first.
- A skill contains non-Markdown files in its resource directories. They are discovered for skill packaging and link
  checks as today, but are not governed by the skills corpus.
- Contradictions expressed through indirect or conditional rules, patterns, optional fields, or interactions
  between repository layers are outside FR-008's detection boundary. They still apply when checking skills.
- A workspace opts out of the built-in schema and has no `skills` spec. Its skills are ungoverned, with no
  error: that is how a workspace opts out of skills governance (FR-018).

## Key Entities

- **Skills corpus:** The reserved corpus whose documents are skills, found by the agents' skills directories
  rather than by a directory under `docs/`.
- **Skills spec:** A spec named `skills` or `skills-<namespace>`, in the same directory and with the same
  files as any other.
- **Built-in skills schema:** The Agent Skills specification's rules, stated as a schema that ships with the tool.
  The `skills` spec extends it unless the workspace opts out.
- **Skill name:** The name of the skill's directory, read as the aspect a namespace and a facet split, as a
  document's name is.

## Success Criteria

- **SC-001:** This repository governs its own skills with a `skills` spec and the `skills-code`,
  `skills-docs` and `skills-feat` namespace specs, and `lorecraft check` passes on it.
- **SC-002:** A workspace with no skills spec reports the same findings on its skills before and after the
  feature.
- **SC-003:** Every frontmatter rule the check applies to a skill appears in the built-in schema's generated
  documentation.
- **SC-004:** For every skill in this repository, `lorecraft inspect` lists the same governing specs a
  reader derives from the skill's name.

## Assumptions

- Namespace specs layer by conjunction for every corpus.
- A skill is a directory in a skills directory holding a `SKILL.md`, and its name is that directory's name.

## References

- [prd-008-structured-checks](prd-008-structured-checks.md) - Related: The structured checks that judge a skill against its specs
