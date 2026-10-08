---
name: "OUT006-missing-section"
description: "A document lacks a section its outline requires"
code: "OUT006"
since: "0.3.0"
---

# missing-section (OUT006)

A document lacks a section its outline requires.

## What it does

Checks for documents that leave out a section their structure specification lists under its `outline` key
without `"optional": true`. The section is expected before the section written where it belongs, or at the
end of the document when no section follows. The entry's `description` is shown as help, and its first
`examples` sample as a note, written under the section's heading.

Only the first place a document stops following its outline is reported, since every section after it is
compared with an entry it was never meant to match; a section that is only written further down is out of
order, not missing. A document that more than one specification governs, such as a corpus and a namespace,
must follow each outline, and is reported once for each it breaks.

## Why is this bad?

An agent that loads the document expects every document of its kind to answer the same questions in the same
sections; a section left out is a question the agent cannot tell is unanswered from one it skipped.

## Example

`docs/__meta__/guide.structure.json`:

```json
{
  "outline": [
    {"section": "Usage", "description": "How to invoke the command."},
    {"section": "Options"}
  ]
}
```

`docs/guide/check.md`:

```markdown
# Check

## Options

`--strict` fails on a warning.
```

## Use instead

Write the section where the outline places it:

```markdown
# Check

## Usage

Run `lorecraft check` from the repository root.

## Options

`--strict` fails on a warning.
```
