---
name: "LC009-invalid-title-pattern"
description: "A structure file's title pattern is not a valid regular expression"
code: "LC009"
since: "0.3.0"
---

# invalid-title-pattern (LC009)

A structure file's title pattern is not a valid regular expression.

## What it does

Checks for structure files whose `title.pattern` does not compile as a regular expression.
Such a file is reported once, at the file, and every document its meta spec governs is listed as skipped in
coverage, with no rule run over it: a document that was not checked is never reported as clean. Every document
the file does not govern is checked as if the file were fixed.

It has no level, so no configuration turns it off, and it is always reported as an error.

## Why is this bad?

Until the file is fixed, the documents it governs are not checked, so a violation in them goes unreported and an
agent loads them unreviewed.

## Example

`docs/__meta__/guide.structure.json`, with an unclosed bracket:

```json
{
  "title": {"pattern": "[A-Z"}
}
```

## Use instead

Write a pattern that compiles:

```json
{
  "title": {"pattern": "^[A-Z]"}
}
```
