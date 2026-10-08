---
name: "LC001-invalid-utf8"
description: "A file is not valid UTF-8"
code: "LC001"
since: "0.3.0"
---

# invalid-utf8 (LC001)

A file is not valid UTF-8.

## What it does

Checks for files whose bytes are not valid UTF-8. Such a file is reported once, at the line of its first invalid
byte, and no rule judges it: every rule reads the file's text, and the file has none.

It has no level, so no configuration turns it off, and it is always reported as an error.

## Why is this bad?

An agent that loads the file reads replacement characters, or nothing, where the bytes do not decode, and no
check can tell whether the rest of the file holds to its specification.

## Example

`docs/guide/setup.md`, saved as Latin-1, so its `é` is the single byte `0xE9`:

```markdown
# Café setup
```

## Use instead

Save the file as UTF-8, where `é` is the two bytes `0xC3 0xA9`:

```markdown
# Café setup
```
