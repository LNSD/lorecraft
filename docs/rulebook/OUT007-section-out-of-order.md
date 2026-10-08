---
name: "OUT007-section-out-of-order"
description: "A section the outline names is written out of the order the outline sets"
code: "OUT007"
since: "0.3.0"
---

# section-out-of-order (OUT007)

A section the outline names is written out of the order the outline sets.

## What it does

Checks for documents that write a section their structure specification lists under its `outline` key in a
place the outline gives to a different section. The section is reported where it stands, which is either
where the outline expects a section the document only writes further down, or after every section the
outline matched, once nothing in the outline is left to place it.

Only the first place a document stops following its outline is reported, since every section after it is
compared with an entry it was never meant to match. A document that more than one specification governs, such
as a corpus and a namespace, must follow each outline, and is reported once for each it breaks.

## Why is this bad?

An agent that loads the document expects every document of its kind to answer the same questions in the same
order; a section out of its place is read before the sections it builds on, or missed by an agent that stops
reading where it expects the section to be.

## Example

`docs/__meta__/guide.structure.json`:

```json
{
  "outline": [
    {"section": "Usage"},
    {"section": "Options"}
  ]
}
```

`docs/guide/check.md`:

```markdown
# Check

## Options

`--strict` fails on a warning.

## Usage

Run `lorecraft check` from the repository root.
```

## Use instead

Write the sections in the order the outline lists them:

```markdown
# Check

## Usage

Run `lorecraft check` from the repository root.

## Options

`--strict` fails on a warning.
```
