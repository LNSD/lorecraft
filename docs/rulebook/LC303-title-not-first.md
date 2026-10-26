---
name: "LC303-title-not-first"
description: "A document a structure file governs opens with a heading that is not its H1 title"
code: "LC303"
since: "0.3.0"
---

# title-not-first (LC303)

A document a structure file governs opens with a heading that is not its H1 title.

## What it does

Checks for documents whose first heading is not a `#` H1, and reports that first heading. Every document a
structure file governs is held to it, with no key to state it: the spec need not mention the
title at all. Only a heading at the top level of the document counts: one inside a list or a blockquote does
not.

A document with no H1 title is not reported here, whatever its headings: it is missing its title, which
`missing-title` reports, and adding one fixes both.

A document that more than one spec governs, such as a corpus and a namespace, is reported once.

## Why is this bad?

An agent reads the title to learn what the document is about before it reads the rest; a section above the title
is read before the agent knows what it belongs to.

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

# Setup
```

## Use instead

Move the title above every section:

```markdown
# Setup

## Install

Install the toolkit, then run it once over the repository.
```
