---
name: "FM002-invalid-yaml"
description: "A frontmatter block is not valid YAML"
code: "FM002"
since: "0.3.0"
---

# invalid-yaml (FM002)

A frontmatter block is not valid YAML.

## What it does

Checks for documents whose structure specification sets a `frontmatter` schema, and for skills, whose
frontmatter block cannot be read as YAML. It is reported on the line the YAML stops being readable, or on the
first line, the one that opens the block, when that line cannot be known, such as for collections nested too
deeply to read.

A document no `frontmatter` schema governs is not checked.

## Why is this bad?

An agent that cannot read the block cannot read any field of it, so a single misplaced character hides the
`name` and `description` it decides on.

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
description: Setup: install the toolkit
---

# Setup
```

## Use instead

Quote a value that holds a `: `:

```markdown
---
name: setup
description: "Setup: install the toolkit"
---

# Setup
```
