---
name: "LC013-untyped-frontmatter-schema"
description: "A structure file's frontmatter schema does not state `\"type\": \"object\"`"
code: "LC013"
since: "0.3.0"
---

# untyped-frontmatter-schema (LC013)

A structure file's frontmatter schema does not state `"type": "object"`.

## What it does

Checks for structure files whose `frontmatter` schema does not state `"type": "object"` at its root. A document's
frontmatter is always a mapping, so a schema that does not say so would accept values no document can hold.
Such a file is reported once, at the file, and every document its meta spec governs is listed as skipped in
coverage, with no rule run over it: a document that was not checked is never reported as clean. Every document
the file does not govern is checked as if the file were fixed.

It has no level, so no configuration turns it off, and it is always reported as an error.

## Why is this bad?

Until the file is fixed, the documents it governs are not checked, so a violation in them goes unreported and an
agent loads them unreviewed.

## Example

`docs/__meta__/guide.structure.json`, with a root that states properties but no type:

```json
{
  "frontmatter": {
    "properties": {"name": {"type": "string"}}
  }
}
```

## Use instead

State the type at the root:

```json
{
  "frontmatter": {
    "type": "object",
    "properties": {"name": {"type": "string"}}
  }
}
```
