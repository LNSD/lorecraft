---
name: "LC003-malformed-structure-file"
description: "A structure file does not follow the structure format"
code: "LC003"
since: "0.3.0"
---

# malformed-structure-file (LC003)

A structure file does not follow the structure format.

## What it does

Checks for structure files that are not JSON, or are JSON that does not follow the structure format: a key the
format does not define, a value of the wrong type, or a count below one.
Such a file is reported once, at the file, and every document its meta spec governs is listed as skipped in
coverage, with no rule run over it: a document that was not checked is never reported as clean. Every document
the file does not govern is checked as if the file were fixed.

It has no level, so no configuration turns it off, and it is always reported as an error.

## Why is this bad?

Until the file is fixed, the documents it governs are not checked, so a violation in them goes unreported and an
agent loads them unreviewed.

## Example

`docs/__meta__/guide.structure.json`, with a key the format does not define:

```json
{
  "max_tokens": 4000
}
```

## Use instead

Use the key the format defines:

```json
{
  "tokens": 4000
}
```
