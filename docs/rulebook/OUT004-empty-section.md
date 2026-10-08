---
name: "OUT004-empty-section"
description: "A section holds no content, under a structure specification that forbids empty sections"
code: "OUT004"
since: "0.3.0"
---

# empty-section (OUT004)

A section holds no content, under a structure specification that forbids empty sections.

## What it does

Checks for headings whose section holds nothing, in documents whose structure specification sets
`empty_sections` to `"forbidden"`. A section ends at the next heading of the same or a higher level, or at the
end of the document; a deeper heading opens a subsection, which is content. Every heading counts, whatever its
level: an empty title and an empty subsection are reported like any other section.

A document that more than one specification governs, such as a corpus and a namespace, is reported once for
each specification that forbids empty sections.

The help follows the section: under the title it asks for the document's content, under a section the outline
requires it asks for what the entry describes, with the entry's first example, and under any other it asks to
omit the section.

## Why is this bad?

An empty section promises content the document does not hold. An agent that reads the heading expects the
section to answer it, and finds nothing; a placeholder left for later reads the same way.

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

## Run

Run the toolkit once over the repository.
```

## Use instead

Write what the section is for, or omit it:

```markdown
# Setup

## Run

Run the toolkit once over the repository.
```
