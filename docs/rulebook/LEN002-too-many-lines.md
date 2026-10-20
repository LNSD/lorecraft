---
name: "LEN002-too-many-lines"
description: "An item is longer than a governing line budget"
code: "LEN002"
since: "0.3.0"
---

# too-many-lines (LEN002)

An item is longer than a governing line budget.

## What it does

Checks each `lines` budget set by the item's governing structure files. A document or spec with no line
budget is not counted. A skill without a structure line budget keeps the 500-line Agent Skills default.

The whole file counts: frontmatter, blank lines and code as much as prose. A file exactly at its budget fits;
the first line after it is reported.

## Why is this bad?

An agent loads the whole file, so every line uses context whether or not the current task needs it.

## Use instead

Split material into a linked document, or into a skill resource under `references/` for skills.
