---
name: "LC210-invalid-frontmatter"
description: "A frontmatter breaks a constraint its schema sets on the whole block"
code: "LC210"
since: "0.3.0"
---

# invalid-frontmatter (LC210)

A frontmatter breaks a constraint its schema sets on the whole block.

## What it does

Checks for documents whose frontmatter breaks a constraint their structure file's `frontmatter`
schema sets on the block rather than on one field. It is reported on line 1, since it concerns no one field. A
block with fewer fields than `minProperties` requires is reported by `too-few-fields`, and one with more than
`maxProperties` allows by `too-many-fields`. A skill's frontmatter is reported here only when the Agent Skills
spec rejects it without naming a field.

A constraint that names a key is not the block's: a key `propertyNames` rejects, and a field whose
`dependentRequired` fields are missing, are reported by `invalid-value` on that key's line.

The help is the description the schema states for the block, when it states one, and the schema's own wording
is shown as a note.

## Why is this bad?

The schema states what the block must hold as a whole so that every document gives an agent the same information; a
block outside it leaves the agent without some of them.

## Example

`docs/__meta__/guide.spec.json`:

```json
{
  "frontmatter": {
    "type": "object",
    "anyOf": [
      {"required": ["summary"]},
      {"required": ["description"]}
    ]
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

Write the block the schema describes:

```markdown
---
description: Install the toolkit and run it once over the repository.
---

# Setup
```
