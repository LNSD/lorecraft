---
name: "spec-structure-frontmatter"
description: "The frontmatter key of a structure file: a Draft 2020-12 JSON Schema for a document's YAML frontmatter whose root states type object, checked against the meta-schema on load, with corpus and namespace schemas applied each on its own. Load when writing or changing a frontmatter schema, adding a frontmatter field, or a frontmatter schema is reported invalid"
type: "feature"
status: "experimental"
components: "module:lorecraft.project,module:lorecraft.checks,spec:feat,spec:code"
---

# Frontmatter Schemas

## Summary

The `frontmatter` key of a `<name>.structure.json` file states the frontmatter rules of the documents its name
governs, as a JSON Schema the frontmatter mapping must satisfy. Unlike the rest of the structure dialect, its
value is JSON Schema Draft 2020-12 itself, so any editor and any JSON Schema tool reads it.
`lorecraft check` applies it with the `FM` rules, as it applies the `tokens` key of the same file.

## Table of Contents

1. [Key Concepts](#key-concepts)
2. [Usage](#usage)
3. [Limitations](#limitations)
4. [References](#references)
5. [Code References](#code-references)

## Key Concepts

- **Frontmatter schema**: The value of the `frontmatter` key; its root describes the frontmatter as one
  object, and must say `"type": "object"` outright.
- **Corpus schema**: The frontmatter schema at the corpus meta spec name, which states the whole field set,
  usually with `required` and `additionalProperties: false`. Without it the corpus's frontmatter is unchecked.
- **Namespace schema**: A frontmatter schema at a namespace meta spec name. It is applied beside the corpus
  schema, never in place of it, so it states only the constraints it adds.

## Usage

### A Corpus Schema

```json
{
  "$schema": "../schemas/structure.spec.json",
  "frontmatter": {
    "type": "object",
    "required": ["name", "description"],
    "additionalProperties": false,
    "properties": {
      "name": { "type": "string", "pattern": "^[a-z0-9]+(?:-[a-z0-9]+)*$" },
      "description": { "type": "string", "pattern": "Load when" }
    }
  },
  "outline": [{ "section": "Summary" }, { "any": true }]
}
```

### A Namespace Schema

A namespace schema leaves out `required` and `additionalProperties`, which the corpus schema already states,
and narrows a field the corpus schema allows. `feat-cli.structure.json` requires a `module:lorecraft.cli` entry
in `components`, for `cli.md` and `cli-*.md` only:

```json
{
  "frontmatter": {
    "type": "object",
    "properties": {
      "components": { "type": "string", "pattern": "(?:^|,)\\s*module:lorecraft\\.cli(?:\\.[a-z0-9_]+)+\\s*(?:,|$)" }
    }
  }
}
```

### Validation on Load

The generated `docs/schemas/structure.spec.json` lets an editor check the key as it is written. When the
repository is loaded, each frontmatter schema is checked against the Draft 2020-12 meta-schema, and refused
when its root does not state `"type": "object"`, when any schema in it carries `$id`, which would change how
a relative `$ref` resolves, or names another dialect in `$schema`. A value under `enum` or `const` is data, not
a schema, so it is not searched. `description` and `$comment` are allowed
anywhere. A refused schema stops the command with an error naming the structure file:
both `lorecraft check` and `lorecraft inspect` exit `2`.

## Limitations

- The schema sees the parsed YAML, so how a value is written, such as whether it is quoted, is invisible to it.
- That `name` matches the filename is a rule of its own, `FM004`, not of any schema, and holds wherever a
  frontmatter schema governs.

## References

- [spec-structure](spec-structure.md) - Base: the file this key belongs to, its layers and its editor schema
- [cli-check](cli-check.md) - Related: the command that applies this schema

## Code References

- `src/lorecraft/project/schemas/structure.py` - The frontmatter schema and its checks on load
- `src/lorecraft/project/schemas/structure_file.py` - The key's shape in the published editor schema
- `src/lorecraft/rules/frontmatter/` - The `FM` rules that apply the schemas to a document's frontmatter
