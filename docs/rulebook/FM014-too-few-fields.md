---
name: "FM014-too-few-fields"
description: "A frontmatter holds fewer fields than its schema requires"
code: "FM014"
since: "0.3.0"
---

# too-few-fields (FM014)

A frontmatter holds fewer fields than its schema requires.

## What it does

Checks for documents whose frontmatter holds fewer fields than their structure file's `frontmatter`
schema requires with `minProperties`. It is reported on line 1, since it concerns no one field. The message says
how many fields the block holds against the least the schema requires, and the help is the description the
schema states for the block, when it states one.

## Why is this bad?

The schema sets a floor on the block so that every document gives an agent the same few facts, and a block under
the floor leaves the agent without some of them.

## Example

`docs/__meta__/guide.spec.json`:

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

Write the fields the schema requires:

```markdown
---
name: setup
description: Install the toolkit and run it once over the repository.
---

# Setup
```
