---
name: "LC005-repeated-outline-section"
description: "A structure file names an outline section more than once"
code: "LC005"
since: "0.3.0"
---

# repeated-outline-section (LC005)

A structure file names an outline section more than once.

## What it does

Checks for structure files whose `outline` names one section more than once, so a document could never hold to it.
Such a file is reported once, at the file, and every document its meta spec governs is listed as skipped in
coverage, with no rule run over it: a document that was not checked is never reported as clean. Every document
the file does not govern is checked as if the file were fixed.

`lorecraft check` does not report this code yet: it stops with exit status 2 at a structure file it cannot
use, so the file is not reported and no document it governs is listed as skipped.

It has no level, so no configuration turns it off, and it is always reported as an error.

## Why is this bad?

Until the file is fixed, the documents it governs are not checked, so a violation in them goes unreported and an
agent loads them unreviewed.

## Example

`docs/__meta__/guide.structure.json`, naming `Overview` twice:

```json
{
  "outline": [
    {"section": "Overview"},
    {"section": "Details"},
    {"section": "Overview"}
  ]
}
```

## Use instead

Name each section once:

```json
{
  "outline": [
    {"section": "Overview"},
    {"section": "Details"}
  ]
}
```
