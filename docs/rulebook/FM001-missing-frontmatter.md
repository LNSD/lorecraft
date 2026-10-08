---
name: "FM001-missing-frontmatter"
description: "A document or a skill does not open with a frontmatter block"
code: "FM001"
since: "0.3.0"
---

# missing-frontmatter (FM001)

A document or a skill does not open with a frontmatter block.

## What it does

Checks for documents whose structure specification sets a `frontmatter` schema, and for skills, whose
`SKILL.md` the Agent Skills specification requires to open with frontmatter, that do not open with a block
between two `---` lines. A file whose first line is not `---`, or whose block is never closed by a second
`---` line, has none.

A document no `frontmatter` schema governs is not checked.

## Why is this bad?

An agent decides whether to load a document or a skill from its frontmatter, its `name` and `description`
among them; without a block it has nothing to decide on, and loads the file blind or never.

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
# Setup

Install the toolkit, then run it once over the repository.
```

## Use instead

Open the file with the block:

```markdown
---
name: setup
description: Install the toolkit and run it for the first time.
---

# Setup

Install the toolkit, then run it once over the repository.
```
