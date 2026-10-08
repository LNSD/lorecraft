---
name: "OUT009-invalid-title"
description: "A document's title does not match the pattern its structure specification sets on `title`"
code: "OUT009"
since: "0.3.0"
---

# invalid-title (OUT009)

A document's title does not match the pattern its structure specification sets on `title`.

## What it does

Checks for an H1 title whose text does not match the `pattern` its structure specification sets on `title`. The
pattern is matched as JSON Schema's `pattern` is: it is searched for anywhere in the title's text, so a pattern
that must hold the whole title anchors itself with `^` and `$`. Only the document's first H1 is its title, and a
document with no title is not reported here.

A document that more than one specification governs, such as a corpus and a namespace, must keep its title to
every pattern they set, and is reported once for each pattern the title does not match.

## Why is this bad?

A pattern states how every title of a corpus reads, so an agent scanning a listing of titles can tell what each
document is; a title that breaks it reads apart from the rest, or hides what the document is about.

## Example

`docs/__meta__/guide.structure.json`:

```json
{
  "title": { "pattern": "^[A-Z][^:]*$" }
}
```

`docs/guide/setup.md`, with a title holding a colon:

```markdown
# Setup: the toolkit on a new machine
```

## Use instead

Write the title the way the pattern states:

```markdown
# Setting up the toolkit
```
