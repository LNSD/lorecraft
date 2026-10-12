---
name: "LC012-foreign-frontmatter-dialect"
description: "A structure file's frontmatter schema names another JSON Schema dialect"
code: "LC012"
since: "0.3.0"
---

# foreign-frontmatter-dialect (LC012)

A structure file's frontmatter schema names another JSON Schema dialect.

## What it does

Checks for structure files whose `frontmatter` schema, or a schema inside it, sets `$schema` to anything but the
2020-12 dialect, the only one a frontmatter schema is written in.
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

`docs/__meta__/guide.structure.json`, written in draft-07:

```json
{
  "frontmatter": {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object"
  }
}
```

## Use instead

Name the 2020-12 dialect, or leave `$schema` out:

```json
{
  "frontmatter": {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object"
  }
}
```
