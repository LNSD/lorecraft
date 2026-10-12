---
name: "LC010-invalid-frontmatter-schema"
description: "A structure file's frontmatter schema is not a valid JSON Schema"
code: "LC010"
since: "0.3.0"
---

# invalid-frontmatter-schema (LC010)

A structure file's frontmatter schema is not a valid JSON Schema.

## What it does

Checks for structure files whose `frontmatter` key is not a valid JSON Schema of the 2020-12 dialect.
Such a file is reported once, at the file, and every document its meta spec governs is listed as skipped in
coverage, with no rule run over it: a document that was not checked is never reported as clean. Every document
the file does not govern is checked as if the file were fixed.

It has no level, so no configuration turns it off, and it is always reported as an error.

## Why is this bad?

Until the file is fixed, the documents it governs are not checked, so a violation in them goes unreported and an
agent loads them unreviewed.

## Example

`docs/__meta__/guide.structure.json`, with `required` holding a string where a list is due:

```json
{
  "frontmatter": {"type": "object", "required": "name"}
}
```

## Use instead

Write the keyword as the dialect defines it:

```json
{
  "frontmatter": {"type": "object", "required": ["name"]}
}
```
