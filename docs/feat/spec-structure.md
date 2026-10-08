---
name: "spec-structure"
description: "The structure file: <name>.structure.json as the machine-checkable half of a meta spec, its $schema and description keys, the rule that a file states at least one rule, how a namespace file adds to the corpus file, what is refused on load, and editor validation with the generated docs/schemas/structure.spec.json. Load when creating a structure file, pointing an editor at the dialect's schema, or one is reported invalid"
type: "feature"
status: "experimental"
components: "module:lorecraft.project,spec:feat,spec:code"
---

# Structure Specification Files

## Summary

A `<name>.structure.json` file holds the rules of a meta spec that a check can decide, for the documents
its name governs. It is a small JSON dialect: each key states one kind of rule, every key is optional, and a
check reads only the keys it applies. A generated JSON Schema of the dialect lets an editor validate a file as
it is written.

## Table of Contents

1. [Key Concepts](#key-concepts)
2. [Configuration](#configuration)
3. [Usage](#usage)
4. [Limitations](#limitations)
5. [References](#references)
6. [Code References](#code-references)

## Key Concepts

- **Structure file**: A `<name>.structure.json` file in `docs/__meta__/`, the machine-checkable half
  of the prose `<name>.md` beside it.
- **Rule key**: A top-level key that states one kind of rule. A file holds any subset of them.
- **Layer**: Each structure file that applies to a document: the corpus file, then every namespace
  file whose name matches, as [spec](spec.md#base-and-extension) resolves them. Every layer is applied on its
  own.
- **Editor schema**: `structure.spec.json`, the JSON Schema of the dialect's shape, generated from the model
  the checks read a file with.

## Configuration

| Key | Value | Meaning |
|-----|-------|---------|
| `$schema` | `"../schemas/structure.spec.json"` | Points an editor at the editor schema; not read by the checks |
| `description` | text | For whoever opens the file; not read by the checks |
| a rule key | set by the key | One kind of rule, read by the check that applies it |

Every key is optional, but a file must state at least one rule. The editor schema lists every key the dialect
has, with its shape.

## Usage

### A Corpus File

```json
{
  "$schema": "../schemas/structure.spec.json",
  "description": "Rules for a rule document in docs/code/.",
  "tokens": 5000
}
```

### A Namespace File

A namespace file is applied beside the corpus file, never in place of it. It states only what it adds, and it
cannot relax what the corpus file says: a document must pass every layer. Here a namespace file tightens the
rule above for the documents its name matches:

```json
{
  "$schema": "../schemas/structure.spec.json",
  "description": "Narrows code.structure.json for docs/code/python-*.md.",
  "tokens": 3000
}
```

### Refused on Load

A file is refused, and the command stops with an error naming it, when it is not JSON, holds a key or a value
type the dialect does not have, or states no rule. A rule key adds refusals of its own, for a value no
document could satisfy or that contradicts another.

### Validating in an Editor

The dialect's shape is published as a JSON Schema, `docs/schemas/structure.spec.json` in the lorecraft
repository, generated from the same model the checks read a file with. Keep a copy at the same path in your
repository, where the `$schema` value above points from `docs/__meta__/`, and an editor validates a structure
file as it is written. It states the shape only; a rule that no shape can state is checked on load.

## Limitations

- A file is selected by a document's path, never by its `type` or any other frontmatter value: its rules apply
  to every document its name governs.
- A layer only adds rules. No key lets a namespace file release a document from the corpus file.

## References

- [spec](spec.md) - Base: meta spec names, file types and how layers apply
- [cli-check](cli-check.md) - Related: the command whose rules read a structure file

## Code References

- `src/lorecraft/project/schemas/structure_file.py` - The file's shape, and the source of the generated schema
- `src/lorecraft/project/schemas/structure.py` - Turns a file into rules, and refuses unusable ones
