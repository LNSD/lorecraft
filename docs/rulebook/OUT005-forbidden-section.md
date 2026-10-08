---
name: "OUT005-forbidden-section"
description: "A section a structure specification forbids appears in the document"
code: "OUT005"
since: "0.3.0"
---

# forbidden-section (OUT005)

A section a structure specification forbids appears in the document.

## What it does

Checks for H2 sections whose heading text is one of the names a document's structure specification lists under
`forbidden`. Only H2 headings are sections: a title or a deeper heading of the same text is not reported. Every
occurrence is reported, so a forbidden section written twice is reported twice.

A document that more than one specification governs, such as a corpus and a namespace, is reported once for
each specification that forbids the section.

## Why is this bad?

A specification forbids a section because what it would hold belongs elsewhere, or nowhere: a changelog kept in
the version history, or a history of the document that an agent reads as a current rule. Written anyway, the
section is read as part of the document.

## Example

`docs/__meta__/guide.structure.json`:

```json
{
  "forbidden": ["Changelog"]
}
```

`docs/guide/setup.md`:

```markdown
# Setup

## Run

Run the toolkit once over the repository.

## Changelog

Added the run step.
```

## Use instead

Remove the section:

```markdown
# Setup

## Run

Run the toolkit once over the repository.
```
