---
name: "LC004-empty-structure-file"
description: "A structure file states no rule"
code: "LC004"
since: "0.3.0"
---

# empty-structure-file (LC004)

A structure file states no rule.

## What it does

Checks for structure files that follow the structure format and state no rule: no title check, no empty-section
ban, no outline, no forbidden sections, no token budget and no frontmatter schema, so the file would check nothing.
Such a file is reported once, at the file, and every document its meta spec governs is listed as skipped in
coverage, with no rule run over it: a document that was not checked is never reported as clean. Every document
the file does not govern is checked as if the file were fixed.

It has no level, so no configuration turns it off, and it is always reported as an error.

## Why is this bad?

Until the file is fixed, the documents it governs are not checked, so a violation in them goes unreported and an
agent loads them unreviewed.

## Example

`docs/__meta__/guide.structure.json`, stating nothing:

```json
{}
```

## Use instead

State the rules the corpus is held to:

```json
{
  "tokens": 4000
}
```
