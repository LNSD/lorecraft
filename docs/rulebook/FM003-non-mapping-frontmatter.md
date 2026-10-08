---
name: "FM003-non-mapping-frontmatter"
description: "A frontmatter block is valid YAML, but not a mapping of fields"
code: "FM003"
since: "0.3.0"
---

# non-mapping-frontmatter (FM003)

A frontmatter block is valid YAML, but not a mapping of fields.

## What it does

Checks for documents whose structure specification sets a `frontmatter` schema, and for skills, whose
frontmatter block reads as YAML but holds something other than `key: value` fields: a list, a single value,
or nothing at all.

A document no `frontmatter` schema governs is not checked.

## Why is this bad?

An agent looks a field such as `name` or `description` up by its key, and a block that is not a mapping has
no keys to look up.

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
- setup
- Install the toolkit and run it for the first time.
---

# Setup
```

## Use instead

Write each field as a key and its value:

```markdown
---
name: setup
description: Install the toolkit and run it for the first time.
---

# Setup
```
