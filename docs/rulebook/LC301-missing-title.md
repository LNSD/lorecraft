---
name: "LC301-missing-title"
description: "A document a structure file governs carries no H1 title"
code: "LC301"
since: "0.3.0"
---

# missing-title (LC301)

A document a structure file governs carries no H1 title.

## What it does

Checks for documents with no `#` H1 heading. Every document a structure file governs is held to it,
with no key to state it: the spec need not mention the title at all. Only a heading at the top level
of the document counts: one inside a list or a blockquote does not.

A document that more than one spec governs, such as a corpus and a namespace, is reported once.

## Why is this bad?

An agent reads the title to learn what the document is about before it reads the rest; without one it has to
guess from the first section, and a link or a listing that shows the title shows nothing.

## Example

`docs/__meta__/guide.spec.json`:

```json
{
  "empty_sections": "forbidden"
}
```

`docs/guide/setup.md`:

```markdown
## Install

Install the toolkit, then run it once over the repository.
```

## Use instead

Open the document with its title:

```markdown
# Setup

## Install

Install the toolkit, then run it once over the repository.
```
