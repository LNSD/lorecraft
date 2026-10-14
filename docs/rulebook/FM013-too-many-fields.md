---
name: "FM013-too-many-fields"
description: "A frontmatter holds more fields than its schema allows"
code: "FM013"
since: "0.3.0"
---

# too-many-fields (FM013)

A frontmatter holds more fields than its schema allows.

## What it does

Checks for documents whose frontmatter holds more fields than their structure file's `frontmatter`
schema allows with `maxProperties`. It is reported on line 1, since it concerns no one field. The message says
how many fields the block holds against the most the schema allows, and the help is the description the schema
states for the block, when it states one.

## Why is this bad?

The schema caps the block so that every document gives an agent the same few facts, and a block past the cap
carries fields the schema did not plan for.

## Example

`docs/__meta__/guide.spec.json`:

```json
{
  "frontmatter": {
    "type": "object",
    "maxProperties": 1
  }
}
```

`docs/guide/setup.md`:

```markdown
---
name: setup
description: Install the toolkit and run it once over the repository.
---

# Setup
```

## Use instead

Keep the fields the schema allows:

```markdown
---
name: setup
---

# Setup
```
