---
name: "LEN004-title-too-many-words"
description: "A document's title is longer than its word cap allows"
code: "LEN004"
since: "0.3.0"
---

# title-too-many-words (LEN004)

A document's title is longer than its word cap allows.

## What it does

Checks for an H1 title longer than the `words` cap its structure specification sets on `title`. The words are
those of the title's own text, counted as a section's prose words are: each whitespace-delimited token is one.
Only the document's first H1 is its title, and a document with no title is not reported here.

A document that more than one specification governs, such as a corpus and a namespace, must keep its title
within every cap they set, and is reported once for each cap the title exceeds.

## Why is this bad?

A title is what an agent reads to decide whether the document is the one it needs; a long one says less, not
more, and costs context in every listing that shows it.

## Example

`docs/__meta__/guide.structure.json`:

```json
{
  "title": { "words": 4 }
}
```

`docs/guide/setup.md`, with a title of ten words:

```markdown
# How to set up the toolkit on a new machine
```

## Use instead

Name what the document is about, and leave the rest to its first paragraph:

```markdown
# Setting up the toolkit
```
