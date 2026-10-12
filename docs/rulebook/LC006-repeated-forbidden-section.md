---
name: "LC006-repeated-forbidden-section"
description: "A structure file forbids a section more than once"
code: "LC006"
since: "0.3.0"
---

# repeated-forbidden-section (LC006)

A structure file forbids a section more than once.

## What it does

Checks for structure files whose `forbidden` list names one section more than once.
Such a file is reported once, at the file, and every document its meta spec governs is listed as skipped in
coverage, with no rule run over it: a document that was not checked is never reported as clean. Every document
the file does not govern is checked as if the file were fixed.

It has no level, so no configuration turns it off, and it is always reported as an error.

## Why is this bad?

Until the file is fixed, the documents it governs are not checked, so a violation in them goes unreported and an
agent loads them unreviewed.

## Example

`docs/__meta__/guide.structure.json`, forbidding `Draft` twice:

```json
{
  "forbidden": ["Draft", "Notes", "Draft"]
}
```

## Use instead

Forbid each section once:

```json
{
  "forbidden": ["Draft", "Notes"]
}
```
