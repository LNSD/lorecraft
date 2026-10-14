---
name: "LC003-malformed-structure-file"
description: "A structure file does not follow the structure format, or states no rule"
code: "LC003"
since: "0.3.0"
---

# malformed-structure-file (LC003)

A structure file does not follow the structure format, or states no rule.

## What it does

Checks for structure files that are not a usable statement of the structure format, in one of two ways: the file
is not JSON, or is JSON that holds a key the format does not define, a value of the wrong type or a count below
one; or the file is in the format and states no rule, so it would check nothing.
Such a file is reported once, at the file, and every document its meta spec governs is listed as skipped in
coverage, with no rule run over it: a document that was not checked is never reported as clean. Every document
the file does not govern is checked as if the file were fixed.

The message says which of the two it is, and for the first, lists every problem found.

It has no level, so no configuration turns it off, and it is always reported as an error.

## Why is this bad?

Until the file is fixed, the documents it governs are not checked, so a violation in them goes unreported and an
agent loads them unreviewed.

## A file that does not follow the format

`docs/__meta__/guide.spec.json`, with a key the format does not define:

```json
{
  "max_tokens": 4000
}
```

Use the key the format defines:

```json
{
  "tokens": 4000
}
```

## A file that states no rule

`docs/__meta__/guide.spec.json`, stating nothing. The file would check no title, no empty section, no
outline, no forbidden section, no token budget and no frontmatter schema:

```json
{}
```

State the rules the corpus is held to, or delete the file:

```json
{
  "tokens": 4000
}
```
