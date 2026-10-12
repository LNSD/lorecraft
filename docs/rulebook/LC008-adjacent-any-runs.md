---
name: "LC008-adjacent-any-runs"
description: "A structure file places two `any` runs side by side in its outline"
code: "LC008"
since: "0.3.0"
---

# adjacent-any-runs (LC008)

A structure file places two `any` runs side by side in its outline.

## What it does

Checks for structure files whose `outline` holds two `any` entries next to each other. Two runs side by side match
exactly what one run matches, so the outline would mean something other than what it says.
Such a file is reported once, at the file, and every document its meta spec governs is listed as skipped in
coverage, with no rule run over it: a document that was not checked is never reported as clean. Every document
the file does not govern is checked as if the file were fixed.

It has no level, so no configuration turns it off, and it is always reported as an error.

## Why is this bad?

Until the file is fixed, the documents it governs are not checked, so a violation in them goes unreported and an
agent loads them unreviewed.

## Example

`docs/__meta__/guide.structure.json`, with two runs in a row:

```json
{
  "outline": [
    {"any": true},
    {"any": true, "words": 200}
  ]
}
```

## Use instead

State one run, with the cap the two together were meant to carry:

```json
{
  "outline": [
    {"any": true, "words": 200}
  ]
}
```
