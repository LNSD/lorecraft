---
name: "prd-018-frontmatter-format"
description: "Frontmatter is plain frontmatter: lorecraft accepts the small set of constructs document metadata is written with, and reports every other construct, and every key written twice, on its line, so what a block means no longer depends on a parser's grammar"
type: "prd"
status: "draft"
---

# Plain Frontmatter

## Problem

A document's or a skill's frontmatter is the metadata an agent decides on: its `name`, its `description` and the
fields a schema asks for. What lorecraft accepted in that block was never written down. It was whatever the parser
underneath took, so a block could carry processing directives, references from one value to another, type
annotations, explicit keys, document markers and collections nested over many lines, and still pass. None of this is
needed to write metadata, and each one makes a block mean something a reader cannot see at a glance: a reference
copies a value from elsewhere, an annotation changes a value's type, a second marker ends the metadata early.

Keeping all of it also ties lorecraft to one parser: changing parser means proving, construct by construct, that the
new one reads every esoteric form the old one did. The frontmatter Jekyll, Hugo, Obsidian and Agent Skills documents
use is much smaller, and lorecraft's own blocks smaller still: one flat mapping of quoted strings.

A key written twice is a related gap. A top-level duplicate is reported today, but in a nested mapping the last value
wins without a word.

## Goals

- What lorecraft accepts as frontmatter is a stated format, the same whichever parser reads it.
- The format covers the frontmatter writers use: nested mappings, lists, short inline lists and mappings, quoted and
  multi-line text, and comments.
- Every construct outside the format is reported on its line, naming what was found.
- A key written twice is reported, whatever its depth.
- Every block inside the format reads to the same value as today.

## Non-Goals

- **Choosing the parser.** How the format is read is a design decision, so it is recorded apart from this PRD, and
  the format holds whichever parser reads it.
- **Changing how values are typed.** A plain value keeps the type it has today (FR-005), so that no block inside the
  format changes its value; only which constructs are accepted changes.
- **Changing what a schema checks.** Missing, unknown, mistyped and invalid fields are judged as before, on the value
  the block reads to: the format decides what a block may hold, a schema what its fields must be.
- **Checking blocks no check reads today.** A document no frontmatter schema governs is still not checked, since
  which documents are checked is decided by their governance, not by the format.

## User Stories

### US-1: Write metadata the way other tools expect it (P1)

As a writer, I want every construct that common frontmatter uses accepted, so that a document written for another
documentation tool passes lorecraft's check unchanged.

**Independent test:** Check documents whose frontmatter uses each accepted construct, alone and combined.

```gherkin
Scenario: Nested metadata and lists
  Given a document whose frontmatter has a nested mapping, a list of items and a short inline list of tags
  When the writer checks the workspace
  Then no frontmatter diagnostic is reported for the document
```

```gherkin
Scenario: Multi-line text
  Given a document whose description is written as a folded block of text over several lines
  When the writer checks the workspace
  Then the description reads as one text value
  And no frontmatter diagnostic is reported for the document
```

### US-2: Be told which construct is not allowed (P1)

As a writer, I want a construct outside the format reported on its line, naming what was found, so that I know what
to remove without reading a parser's grammar.

**Independent test:** Check one document per refused construct, each otherwise valid.

```gherkin
Scenario: A reference to another value
  Given a document whose frontmatter defines a value once and refers to it from another key
  When the writer checks the workspace
  Then an invalid-YAML diagnostic is reported on the line of the first reference construct
  And its message names the construct found and says frontmatter does not allow it
```

```gherkin
Scenario: A directive before the metadata
  Given a document whose frontmatter opens with a directive line
  When the writer checks the workspace
  Then an invalid-YAML diagnostic is reported on the directive's line
```

### US-3: Catch a key written twice (P2)

As a writer, I want a key written twice reported at any depth, so that no value I wrote is silently dropped.

**Independent test:** Check a document whose nested mapping writes one key twice.

```gherkin
Scenario: A duplicate in a nested mapping
  Given a document whose frontmatter has a nested mapping that writes the same key twice
  When the writer checks the workspace
  Then a duplicate-key diagnostic is reported on the later key's line, pointing back at the first
```

## Requirements

- **FR-001:** THE SYSTEM SHALL accept a frontmatter block whose top level is a mapping written one key per line,
  whose keys are plain or quoted text, and whose values may themselves be such mappings.
- **FR-002:** THE SYSTEM SHALL accept lists written one item per line, whose items are values, inline lists or
  mappings, or mappings written one key per line.
- **FR-003:** THE SYSTEM SHALL accept a list or a mapping written inline on one line, such as `[a, b]` or
  `{a: 1}`, when it holds no other list or mapping.
- **FR-004:** THE SYSTEM SHALL accept values written plain, in single or double quotes, or as literal (`|`) or
  folded (`>`) blocks with or without a strip (`-`) or keep (`+`) indicator; a plain or quoted value may continue on
  the lines below.
- **FR-005:** THE SYSTEM SHALL read a plain value as null, a boolean, an integer or a float when its whole text is
  one, as today, and as text otherwise, so `yes` and `2026-10-05` are text.
- **FR-006:** THE SYSTEM SHALL accept comments, blank lines, Windows line endings and a byte-order mark in a
  frontmatter block.
- **FR-007:** IF a frontmatter block holds a directive, or a document start or end marker inside it, THEN THE SYSTEM
  SHALL report an invalid-YAML diagnostic on that line.
- **FR-008:** IF a frontmatter block holds a reference construct (an anchor, an alias or a merge key), THEN THE
  SYSTEM SHALL report an invalid-YAML diagnostic on that line.
- **FR-009:** IF a frontmatter block holds a type annotation (a tag), THEN THE SYSTEM SHALL report an
  invalid-YAML diagnostic on that line.
- **FR-010:** IF a frontmatter block holds an explicit key entry (`? key`), an empty key or a key that is not text,
  THEN THE SYSTEM SHALL report an invalid-YAML diagnostic on that line.
- **FR-011:** IF a frontmatter block holds an inline list or mapping that spans lines, holds another list or
  mapping, or is the block's top level, THEN THE SYSTEM SHALL report an invalid-YAML diagnostic on the line
  it starts.
- **FR-012:** IF a frontmatter block holds a block value with an indentation indicator (`|2`), THEN THE SYSTEM SHALL
  report an invalid-YAML diagnostic on that line.
- **FR-013:** THE SYSTEM SHALL word each diagnostic of FR-007 to FR-012 and FR-016 as `found <what>, which
  frontmatter does not allow`, naming the construct.
- **FR-014:** IF a mapping at any depth writes a key twice, THEN THE SYSTEM SHALL report a duplicate-key diagnostic
  on the later key's line, pointing back at the first, and still check the block's other fields.
- **FR-015:** IF a frontmatter block cannot be read inside the format, THEN THE SYSTEM SHALL report an
  invalid-YAML diagnostic on the line the writer fixes, in its own words naming what is wrong and how to fix
  it, never in the parser's.
- **FR-016:** IF a list written one item per line holds, as an item, another list written one item per line, THEN
  THE SYSTEM SHALL report an invalid-YAML diagnostic on that item's line.
- **NFR-001:** THE SYSTEM SHALL read every block inside the format to the value it reads to today.
- **NFR-002:** THE SYSTEM SHALL carry, for every construct FR-007 to FR-012 and FR-016 refuse, a block that
  triggers its diagnostic and an accepted block that differs from it by the least.

## Edge Cases

- **A block uses two refused constructs.** It is reported on the first one; the second shows once the first is fixed.
- **The first line of a block is a directive followed by a document start marker.** It is refused on the directive's
  line (FR-007): metadata never needs a second document inside its block.
- **A key is a quoted number, such as `"2026"`.** It is text, so it is accepted (FR-001); `2026` unquoted is a key
  that is not text and is refused (FR-010).
- **The top level is an inline mapping on one line**, such as `{name: a}`. It is refused (FR-011): the top level
  is always written one key per line.
- **A list holds a list.** Written one item per line inside another, it is refused (FR-016); as an inline list on
  one item's line, such as `- [a, b]`, it is accepted (FR-002).
- **A block cannot be read because a quote is never closed.** It is reported on the line the quote opens on, where
  the writer fixes it, not where the block ends (FR-015).

## Key Entities

- **Plain frontmatter:** The format of FR-001 to FR-006: what a frontmatter block may hold.
- **Refused construct:** A construct outside the format, reported on its line by name (FR-007 to FR-013, FR-016).
- **Invalid-YAML diagnostic:** The `FM002 invalid-yaml` diagnostic, reported for a block that is outside the
  format or cannot be read.
- **Duplicate-key diagnostic:** The `FM005 duplicate-key` diagnostic, reported for a key written twice at any
  depth (FR-014).

## Success Criteria

- **SC-001:** Every frontmatter block in lorecraft's own repository reads to the same value as before.
- **SC-002:** Every refused construct of FR-007 to FR-012 and FR-016 has a test that reports it on its line,
  named by the construct.
- **SC-003:** A key written twice is reported at the top level and in a nested mapping.
- **SC-004:** The format is stated in one place, and the parser's record refers to it rather than defining it.

## Assumptions

- The format is a subset of the syntax frontmatter is already written in, not a new syntax, so a block that
  lorecraft accepts is one other tools that read frontmatter can read too.
- No document in lorecraft's own repository uses a construct this PRD refuses.

## References

- [prd-008](prd-008-structured-checks.md) - Foundation: The codes and diagnostics this PRD reports under
- [adr-019](adr-019-frontmatter-format.md) - Leads to: How the format is decided and its diagnostics reported
