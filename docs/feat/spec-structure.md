---
name: "spec-structure"
description: "The structure dialect: a <stem>.structure.json file states a document's H1 title rule, section outline with optional sections and any runs, empty and forbidden sections, per-section word caps and whole-file token budget, is refused on load when its rules are unusable, and is validated in editors by the generated docs/schemas/structure.spec.json. Load when writing or changing a structure specification, or one is reported invalid"
type: "feature"
status: "experimental"
components: "module:lorecraft.project.schemas.structure,module:lorecraft.project.schemas.structure_file,module:lorecraft.checks.structure,module:lorecraft.checks.budget,spec:feat,spec:code"
---

# Structure Specification Files

## Summary

A `<stem>.structure.json` file states the section rules of the documents its stem governs: the title, the
order of the sections, which may be empty or must not appear, how many prose words each may hold, and how many
tokens the whole file may hold. A section order cannot be said in JSON Schema, so this is a small dialect of
its own, with a generated JSON Schema that lets an editor validate it as it is written.

## Table of Contents

1. [Key Concepts](#key-concepts)
2. [Configuration](#configuration)
3. [Usage](#usage)
4. [Limitations](#limitations)
5. [References](#references)
6. [Code References](#code-references)

## Key Concepts

- **Outline**: The order of a document's H2 sections, matched left to right.
- **`any` run**: An outline entry matching any number of sections the outline does not name. The run stops at
  a named section, wherever that section's entry sits.
- **Word cap**: The most prose words a section may hold, its H3 subsections included; fenced code and table
  rows are not counted. On an `any` entry it caps each section of the run alone.
- **Token budget**: The most `o200k_base` tokens the whole file may hold, frontmatter, code and tables
  included.

## Configuration

| Key | Value | Meaning |
|-----|-------|---------|
| `$schema` | `"../schemas/structure.spec.json"` | Points an editor at the dialect's JSON Schema; not read by the checks |
| `description` | text | For whoever opens the file; not read by the checks |
| `title` | `{"count": <n>, "first": <bool>}` | How many H1 titles a document holds, and whether one comes before any section |
| `empty_sections` | `"forbidden"` | Every heading must have content under it |
| `tokens` | integer | The token budget, applied by `lorecraft check budget` |
| `outline` | list of entries | `{"section": "<name>"}`, with `"optional": true` when it may be left out, or `{"any": true}`; either may add `"words": <n>` |
| `forbidden` | list of names | Sections that must not appear anywhere |

Every key is optional, but a file must state at least one rule. Every number is at least `1`.

## Usage

### A Corpus Specification

```json
{
  "$schema": "../schemas/structure.spec.json",
  "description": "Section structure for a rule document in docs/code/.",
  "title": { "count": 1, "first": true },
  "empty_sections": "forbidden",
  "tokens": 5000,
  "outline": [
    { "any": true, "words": 350 },
    { "section": "Checklist", "words": 250 },
    { "section": "References", "optional": true }
  ]
}
```

### A Namespace Specification

A namespace specification is applied beside the corpus one, so it states only what it adds. Here
`feat-cli.structure.json` makes `Configuration` required and caps it, and leaves where it sits to the corpus
outline by surrounding it with `any` runs:

```json
{
  "$schema": "../schemas/structure.spec.json",
  "outline": [
    { "any": true },
    { "section": "Configuration", "words": 150 },
    { "any": true }
  ]
}
```

### Refused on Load

A file is refused, and the command stops with an error naming it, when it is not JSON, holds a key or a value
type the dialect does not have, states no rule, sets a number below `1`, names a section twice in its outline,
places two `any` runs side by side, or forbids a section its own outline names.

### Validating in an Editor

The dialect's shape is published as a JSON Schema, `docs/schemas/structure.spec.json` in the lorecraft
repository, generated from the same model the checks read a file with. Keep a copy beside your specifications
and point `$schema` at it, and an editor validates a structure specification as it is written. It states the
shape only; the rules above that no shape can state are checked on load.

## Limitations

- The outline names H2 sections only; H3 subsections are counted in words, never required or ordered.
- A section is matched on its exact heading text.
- Structure is not selected by a document's `type`: one outline applies to every document a stem governs.

## References

- [spec](spec.md) - Base: stems, aspects and how layers apply
- [cli-check-structure](cli-check-structure.md) - Related: the check that applies the outline and the caps
- [cli-check-budget](cli-check-budget.md) - Related: the check that applies the token budget

## Code References

- `src/lorecraft/project/schemas/structure_file.py` - The file's shape, and the source of the generated schema
- `src/lorecraft/project/schemas/structure.py` - Turns a file into rules, and refuses unusable ones
