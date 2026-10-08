---
name: "FM007-unknown-field"
description: "A frontmatter holds a field its schema does not define"
code: "FM007"
since: "0.3.0"
---

# unknown-field (FM007)

A frontmatter holds a field its schema does not define.

## What it does

Checks for documents whose frontmatter holds a field their structure specification's `frontmatter` schema
neither names in `properties` nor matches in `patternProperties`, when the schema sets `additionalProperties`
to `false`, or that no keyword of the schema evaluates, when it sets `unevaluatedProperties` to `false`; and
for skills whose frontmatter holds a field the Agent Skills specification does not define. A document that
several specifications govern is reported once for each schema that does not define the field.

The fields the schema defines are listed as a note: the `properties` of the schema that holds the keyword, or
the fields of the Agent Skills specification. A schema that composes others with `allOf` or `$ref` may
evaluate fields its own `properties` leave out, so for such a schema the list can be shorter than what it
accepts, and it is left out when the schema names none.

## Why is this bad?

An agent reads every field of the frontmatter, so a field no schema defines costs it tokens and offers a fact
no other document states the same way, often a misspelling of a field the schema does define.

## Example

`docs/__meta__/guide.structure.json`:

```json
{
  "frontmatter": {
    "type": "object",
    "properties": {"name": {"type": "string"}, "description": {"type": "string"}},
    "additionalProperties": false
  }
}
```

`docs/guide/setup.md`:

```markdown
---
name: setup
desc: Install the toolkit and run it once over the repository.
---

# Setup
```

## Use instead

Spell the field as the schema defines it:

```markdown
---
name: setup
description: Install the toolkit and run it once over the repository.
---

# Setup
```
