---
name: "spec-header"
description: "The header dialect: a <stem>.header.json file is a Draft 2020-12 JSON Schema for a document's YAML frontmatter, validated against the meta-schema on load, with corpus and namespace schemas applied each on its own. Load when writing or changing a header schema, adding a frontmatter field, or a header schema is reported invalid"
type: "feature"
status: "experimental"
components: "module:lorecraft_project.schemas.header,module:lorecraft.checks.header,spec:feat,spec:code"
---

# Header Specification Files

## Summary

A `<stem>.header.json` file states the frontmatter rules of the documents its stem governs, as a JSON Schema
the frontmatter mapping must satisfy. The dialect is JSON Schema Draft 2020-12 itself, so any editor and any
JSON Schema tool reads it. `lorecraft check header` applies it.

## Table of Contents

1. [Key Concepts](#key-concepts)
2. [Usage](#usage)
3. [Limitations](#limitations)
4. [References](#references)
5. [Code References](#code-references)

## Key Concepts

- **Header schema**: A `<stem>.header.json` file; its top level describes the frontmatter as one object.
- **Corpus schema**: The header schema at the corpus stem, which states the whole field set, usually with
  `required` and `additionalProperties: false`.
- **Namespace schema**: A header schema at a namespace stem. It is applied beside the corpus schema, never in
  place of it, so it states only the constraints it adds.

## Usage

### A Corpus Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "feat.header.json",
  "type": "object",
  "required": ["name", "description"],
  "additionalProperties": false,
  "properties": {
    "name": { "type": "string", "pattern": "^[a-z0-9]+(?:-[a-z0-9]+)*$" },
    "description": { "type": "string", "pattern": "Load when" }
  }
}
```

### A Namespace Schema

A namespace schema leaves out `required` and `additionalProperties`, which the corpus schema already states,
and narrows a field the corpus schema allows. `feat-cli.header.json` requires a `module:lorecraft.cli` entry
in `components`, for `cli.md` and `cli-*.md` only:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "feat-cli.header.json",
  "type": "object",
  "properties": {
    "components": { "type": "string", "pattern": "(?:^|,)\\s*module:lorecraft\\.cli(?:\\.[a-z0-9_]+)+\\s*(?:,|$)" }
  }
}
```

### Validation on Load

Each header schema is checked against the Draft 2020-12 meta-schema when the repository is loaded. A schema the
meta-schema rejects, or a file that is not a JSON object, stops the command with an error naming the file:
`lorecraft check` exits `2` and `lorecraft inspect` exits `1`.

## Limitations

- The schema sees the parsed YAML, so how a value is written, such as whether it is quoted, is invisible to it.
- That `name` matches the filename is a rule of the check, not of any schema, and holds wherever a header
  schema governs.

## References

- [spec](spec.md) - Base: stems, aspects and how layers apply
- [cli-check-header](cli-check-header.md) - Related: the check that applies this dialect

## Code References

- `packages/lorecraft-project/src/lorecraft_project/schemas/header.py` - The dialect and its meta-schema check
- `packages/lorecraft/src/lorecraft/checks/header.py` - Applies the schemas to a document's frontmatter
