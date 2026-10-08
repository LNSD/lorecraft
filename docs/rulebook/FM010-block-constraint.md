---
name: "FM010-block-constraint"
description: "A frontmatter breaks a constraint its schema sets on the whole block"
code: "FM010"
since: "0.3.0"
---

# block-constraint (FM010)

A frontmatter breaks a constraint its schema sets on the whole block.

## What it does

Checks for documents whose frontmatter breaks a constraint their structure specification's `frontmatter`
schema sets on the block rather than on one field, such as `minProperties` or `maxProperties`. It is reported
on line 1, since it concerns no one field. A skill's frontmatter is reported here only when the Agent Skills
specification rejects it without naming a field.

A constraint that names a key is not the block's: a key `propertyNames` rejects, and a field whose
`dependentRequired` fields are missing, are reported by `invalid-value` on that key's line.

The label says how many fields the block holds against the limit, for `minProperties` and `maxProperties`, and
the help is the description the schema states for the block, when it states one. The validator's own wording
is shown as a note only for another keyword.

## Why is this bad?

The schema states what the block must hold as a whole so that every document gives an agent the same facts; a
block outside it leaves the agent without some of them.

## Example

`docs/__meta__/guide.structure.json`:

```json
{
  "frontmatter": {
    "type": "object",
    "minProperties": 2
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
name: setup
description: Install the toolkit and run it once over the repository.
---

# Setup
```
