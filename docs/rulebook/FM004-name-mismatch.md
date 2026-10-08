---
name: "FM004-name-mismatch"
description: "A frontmatter `name` differs from the name its document or skill is found under"
code: "FM004"
since: "0.3.0"
---

# name-mismatch (FM004)

A frontmatter `name` differs from the name its document or skill is found under.

## What it does

Checks for documents whose structure specification sets a `frontmatter` schema and whose `name` differs from
their filename without its extension, and for skills whose `name` differs from the name of their directory,
as the Agent Skills specification requires. A skill's directory is named as an agent lists it in its skills
directory: when that directory is a link to a directory named otherwise, the listed name is the one expected.

Only a `name` written as a string is compared. A `name` that is missing or of another type is the schema's to
report, so a document whose schema does not require `name` may leave it out.

## Why is this bad?

An agent knows a document or a skill by the name it finds it under, and by the `name` it reads; when the two
differ, a reference by one name does not reach the file known by the other.

## Example

`docs/__meta__/guide.structure.json`:

```json
{
  "frontmatter": {
    "type": "object",
    "required": ["name"]
  }
}
```

`docs/guide/setup.md`:

```markdown
---
name: installation
---

# Setup
```

## Use instead

Set `name` to the filename, or rename the file:

```markdown
---
name: setup
---

# Setup
```
