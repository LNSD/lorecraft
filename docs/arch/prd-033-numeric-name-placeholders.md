---
name: "prd-033-numeric-name-placeholders"
description: "Require zero runs in corpus and namespace spec names to match equally wide numeric document-name prefixes, so numbered records are governed as intended."
type: "prd"
status: "draft"
---

# Numeric Name Placeholders

## Problem

Writers who organize governed records with numeric prefixes cannot express their document names through a spec name that reserves the number's width. A corpus spec named `adr-0000.md` is intended to govern records such as `0001-subject.md`, but the names do not share the current literal hyphen-delimited prefix. A namespace spec such as `adr-0000-nspace.md` likewise needs to govern `0001-nspace-subject.md`. Without this matching behavior, numbered documents can be left outside the governance the writer intended.

## Goals

- Let a run of zeroes in a corpus or namespace spec name stand for a numeric document-name prefix of exactly the same width.
- Make the behavior clear with corpus and namespace examples.
- Keep numbering a naming convention chosen by repository writers, with gaps allowed and no ordering validation by Lorecraft.

## Non-Goals

- Requiring documents to be numbered: some corpora use names without numeric prefixes, and that convention remains valid.
- Requiring consecutive numbers or checking that records appear in numeric order: gaps and ordering choices belong to repository writers.
- Defining how name matching is implemented: that is a design decision.

## User Stories

### US-1: Govern numbered records by a width placeholder (P1)

As a repository writer, I want a zero run in a corpus or namespace spec name to stand for an equally wide number, so that numbered records receive the intended rules.

**Independent test:** Inspect or check a corpus with a numeric placeholder in its corpus spec name and a document whose leading numeric segment has the same width.

```gherkin
Scenario: Corpus placeholder matches a four-digit record prefix
  Given a corpus governed by `adr-0000.md`
  And the corpus contains `0001-subject.md`
  When the writer checks the corpus
  Then `0001-subject.md` is governed by the corpus spec
```

```gherkin
Scenario: Namespace placeholder matches the corresponding numbered namespace
  Given a corpus governed by `adr-0000.md`
  And it has the namespace spec `adr-0000-nspace.md`
  And the corpus contains `0001-nspace-subject.md`
  When the writer checks the corpus
  Then `0001-nspace-subject.md` is governed by the corpus and namespace specs
```

### US-2: Keep sequence policy with the repository (P1)

As a repository writer, I want gaps in numeric prefixes to remain valid, so that numbering can reflect my editorial history without Lorecraft imposing an order.

**Independent test:** Check a corpus whose numbered documents have gaps and are not listed in numeric order.

```gherkin
Scenario: Gaps and chosen ordering are accepted
  Given a corpus with matching rules for `0001-first.md` and `0003-third.md`
  And the documents are listed in a different order
  When the writer checks the corpus
  Then neither the gap nor the listing order is reported as an error
```

## Requirements

- **FR-001:** WHEN a corpus or namespace spec name contains a run of zeroes as a numeric placeholder, THE SYSTEM SHALL match that run to a numeric document-name prefix containing exactly the same number of digits.
- **FR-002:** WHEN a corpus spec named `adr-0000.md` governs a document named `0001-<subject>.md`, THE SYSTEM SHALL apply that corpus spec to the document.
- **FR-003:** WHEN a namespace spec named `adr-0000-nspace.md` governs a document named `0001-nspace-<subject>.md`, THE SYSTEM SHALL apply that namespace spec to the document.
- **FR-004:** THE SYSTEM SHALL treat numeric ordering and consecutiveness as repository conventions, allow gaps, and perform no validation of document ordering.

## Success Criteria

- **SC-001:** A writer can use `adr-0000.md` for `0001-<subject>.md` and `adr-0000-nspace.md` for `0001-nspace-<subject>.md`, with the intended specs applied.
- **SC-002:** A writer can leave gaps in numbered document names without receiving an ordering or consecutiveness error.

## References

- [adr-025](adr-025-name-chain-model.md) - Foundation: Existing name-chain matching across corpus documents and specification namespaces
