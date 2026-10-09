---
name: "FM008-wrong-type"
description: "A frontmatter field's value is of a type its schema does not accept"
code: "FM008"
since: "0.3.0"
---

# wrong-type (FM008)

A frontmatter field's value is of a type its schema does not accept.

## What it does

Checks for documents whose frontmatter gives a field a value of a type other than the one the `type` keyword of
its property states in their structure specification's `frontmatter` schema, and for skills whose frontmatter
gives a field a value other than the string, or the mapping of strings to strings for `metadata`, the Agent
Skills specification requires. A value of the right type that breaks another constraint, such as a length
limit, is not this rule's.

The label says the types expected and the type found. A number or a boolean written where a string is
expected is the usual YAML pitfall, as in `version: 1.0`, so the help says to quote it; the field's
`description`, when the schema states one, is shown as help too, and its `example` as a note.

## Why is this bad?

An agent and every tool that reads the field expect the type the schema states, so a value of another type,
such as a list where a string belongs, is misread or dropped.

## Example

`docs/__meta__/guide.structure.json`:

```json
{
  "frontmatter": {
    "type": "object",
    "properties": {"description": {"type": "string"}}
  }
}
```

`docs/guide/setup.md`:

```markdown
---
description:
  - Install the toolkit.
  - Run it once over the repository.
---

# Setup
```

## Use instead

Write the value as the type the schema states:

```markdown
---
description: Install the toolkit, then run it once over the repository.
---

# Setup
```
