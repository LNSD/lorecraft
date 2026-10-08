---
name: "FM005-duplicate-key"
description: "A top-level frontmatter key is written more than once"
code: "FM005"
since: "0.3.0"
---

# duplicate-key (FM005)

A top-level frontmatter key is written more than once.

## What it does

Checks for documents whose structure specification sets a `frontmatter` schema, and for skills, whose
frontmatter writes a top-level key again. Each later occurrence is reported on its own line, pointing back at
the first, whether the values are equal or differ.

A document no `frontmatter` schema governs is not checked.

## Why is this bad?

YAML keeps the value of the last occurrence without a word, so an agent reads whichever was written last, and
one of the two lines says nothing the document means.

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
description: Install the toolkit.
description: Install the toolkit and run it for the first time.
---

# Setup
```

## Use instead

Keep the one value meant:

```markdown
---
name: setup
description: Install the toolkit and run it for the first time.
---

# Setup
```
