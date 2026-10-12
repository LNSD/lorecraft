---
name: "LC007-forbidden-outline-section"
description: "A structure file forbids a section its own outline names"
code: "LC007"
since: "0.3.0"
---

# forbidden-outline-section (LC007)

A structure file forbids a section its own outline names.

## What it does

Checks for structure files whose `forbidden` list names a section that the same file's `outline` names, so no
document could hold to both.
Such a file is reported once, at the file, and every document its meta spec governs is listed as skipped in
coverage, with no rule run over it: a document that was not checked is never reported as clean. Every document
the file does not govern is checked as if the file were fixed.

It has no level, so no configuration turns it off, and it is always reported as an error.

## Why is this bad?

Until the file is fixed, the documents it governs are not checked, so a violation in them goes unreported and an
agent loads them unreviewed.

## Example

`docs/__meta__/guide.structure.json`, requiring and forbidding `Overview`:

```json
{
  "outline": [{"section": "Overview"}],
  "forbidden": ["Overview"]
}
```

## Use instead

Keep the section in one of the two:

```json
{
  "outline": [{"section": "Overview"}],
  "forbidden": ["Draft"]
}
```
