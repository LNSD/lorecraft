---
name: "OUT008-unexpected-section"
description: "A section the outline does not name, in a place the outline does not allow one"
code: "OUT008"
since: "0.3.0"
---

# unexpected-section (OUT008)

A section the outline does not name, in a place the outline does not allow one.

## What it does

Checks for documents that write a section their structure specification's `outline` does not name, in a place
no `{"any": true}` entry of the outline covers. The section is reported where it stands, which is either where
the outline expects a section the document only writes further down, or after the outline's end.

Only the first place a document stops following its outline is reported, since every section after it is
compared with an entry it was never meant to match. A document that more than one specification governs, such
as a corpus and a namespace, must follow each outline, and is reported once for each it breaks.

## Why is this bad?

An agent that loads the document expects every document of its kind to answer the same questions under the
same headings; a section the outline does not name holds content no other document of the kind puts there, so
an agent looking for it in its usual place does not find it.

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

## Usage

Run `lorecraft check` from the repository root.

## Tips

`--strict` fails on a warning.

## Options

`--quiet` prints nothing on success.
```

## Use instead

Move the content under a section the outline names:

```markdown
# Check

## Usage

Run `lorecraft check` from the repository root.

## Options

`--strict` fails on a warning.

`--quiet` prints nothing on success.
```
