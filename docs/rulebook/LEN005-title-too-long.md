---
name: "LEN005-title-too-long"
description: "A document's title is longer than its character cap allows"
code: "LEN005"
since: "0.3.0"
---

# title-too-long (LEN005)

A document's title is longer than its character cap allows.

## What it does

Checks for an H1 title longer than the `chars` cap its structure specification sets on `title`. The characters
are those of the title's own text, without its `#` marker or inline markup, counted as Unicode code points: a
space is one, and so is each code point of an emoji built of several. Only the document's first H1 is its title,
and a document with no title is not reported here.

A document that more than one specification governs, such as a corpus and a namespace, must keep its title
within every cap they set, and is reported once for each cap the title exceeds.

## Why is this bad?

A title is what an agent or a reader scans when documents are listed by title; a wide one overflows the
listing, and a word cap alone does not bound it when a few of its words are long, such as a command or a path.

## Example

`docs/__meta__/guide.structure.json`:

```json
{
  "title": { "chars": 24 }
}
```

`docs/guide/setup.md`, with a title of 36 characters, its backticks not counted:

```markdown
# Setting up `lorecraft check structure`
```

## Use instead

Name what the document is about, and leave the rest to its first paragraph:

```markdown
# Setting up the checks
```
