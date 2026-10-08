---
name: "FM009-invalid-value"
description: "A frontmatter field's value breaks a constraint its schema sets"
code: "FM009"
since: "0.3.0"
---

# invalid-value (FM009)

A frontmatter field's value breaks a constraint its schema sets.

## What it does

Checks for documents whose frontmatter gives a field a value that breaks a constraint of its property in their
structure specification's `frontmatter` schema other than its type, such as `maxLength`, `pattern` or `enum`,
and for skills whose frontmatter breaks such a constraint of the Agent Skills specification, such as a `name`
longer than 64 characters or not in lowercase. Anything wrong inside a field's value, such as a key a mapping
lacks or an item of the wrong type, is that field's value at fault, and is reported here on the field's line,
the top-level key's, since a key nested in a value has no line of its own. A key the schema's `propertyNames`
rejects, or whose `dependentRequired` fields are not all written, is reported here on its own line.

The label says which constraint the value broke, for an `enum`, a `const` or a `pattern`. The help is the reason
the failing subschema gives in its `$comment`, which this repository's schemas use to say why a branch is there,
or else the property's `description`; the allowed values and the property's first example follow. The
validator's own wording is shown as a note only for another keyword.

## Why is this bad?

The schema states the constraint so that every document's field reads the same way to an agent; a value
outside it, such as a description too long to list or a name a tool cannot match, breaks that.

## Example

`docs/__meta__/guide.structure.json`:

```json
{
  "frontmatter": {
    "type": "object",
    "properties": {"name": {"type": "string", "pattern": "^[a-z-]+$"}}
  }
}
```

`docs/guide/setup.md`:

```markdown
---
name: Setup Guide
---

# Setup
```

## Use instead

Write a value within the constraint:

```markdown
---
name: setup-guide
---

# Setup
```
