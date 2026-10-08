---
name: "FM006-missing-field"
description: "A frontmatter lacks a field its schema requires"
code: "FM006"
since: "0.3.0"
---

# missing-field (FM006)

A frontmatter lacks a field its schema requires.

## What it does

Checks for documents whose frontmatter lacks a field the `required` list of their structure specification's
`frontmatter` schema names, and for skills whose frontmatter lacks a field the Agent Skills specification
requires, `name` or `description`. A document that several specifications govern, such as a corpus and a
namespace, is held to each schema they state, and is reported once for each schema that requires the field.

What the schema states about the field is shown as the help to write it: its `description`, the values its
`enum` or `const` allows, and as a note its first `examples` entry. A `required` that sits in a branch, such as
a `then`, leaves the field's `properties` to the schema around it, so nothing is shown for it.

## Why is this bad?

An agent chooses which document or skill to load from its frontmatter alone, so a field left out is a fact the
agent never sees and cannot choose by.

## Example

`docs/__meta__/guide.structure.json`:

```json
{
  "frontmatter": {
    "type": "object",
    "required": ["name", "description"]
  }
}
```

`docs/guide/setup.md`:

```markdown
---
name: setup
---

# Setup
```

## Use instead

Write the field the schema requires:

```markdown
---
name: setup
description: Install the toolkit and run it once over the repository.
---

# Setup
```
