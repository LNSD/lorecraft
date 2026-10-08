---
name: "OUT002-extra-title"
description: "A document a structure specification governs carries more than one H1 title"
code: "OUT002"
since: "0.3.0"
---

# extra-title (OUT002)

A document a structure specification governs carries more than one H1 title.

## What it does

Checks for documents with more than one `#` H1 heading, and reports each H1 after the first at its own heading,
pointing back at the first: the first is the document's title, and every one after it is extra. Every document
a structure specification governs is held to it, with no key to state it: the specification need not mention
the title at all. Only a heading at the top level of the document counts: one inside a list or a blockquote does
not.

A document that more than one specification governs, such as a corpus and a namespace, has each extra title
reported once.

## Why is this bad?

An agent reads the title to learn what the document is about; a second title reads as a second document, so the
agent cannot tell which one the document is, nor that the sections under the second belong to the first.

## Example

`docs/__meta__/guide.structure.json`:

```json
{
  "empty_sections": "forbidden"
}
```

`docs/guide/setup.md`:

```markdown
# Setup

## Install

Install the toolkit, then run it once over the repository.

# Usage

Run it over the repository's documents.
```

## Use instead

Keep one title, and make the rest sections:

```markdown
# Setup

## Install

Install the toolkit, then run it once over the repository.

## Usage

Run it over the repository's documents.
```
