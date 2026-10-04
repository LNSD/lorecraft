---
name: "spec-structure-outline"
description: "The outline keys of a structure specification: the title rule for H1 headings, the outline of H2 sections with required, optional and any entries, empty_sections and forbidden sections, how a namespace outline adds to the corpus outline, and which outlines are refused on load. Load when writing or changing a section outline, requiring, ordering or forbidding a section, or an outline is reported invalid"
type: "feature"
status: "experimental"
components: "module:lorecraft.project,module:lorecraft.checks,spec:feat,spec:code"
---

# Section Outline Rules

## Summary

The `title`, `outline`, `empty_sections` and `forbidden` keys of a `<name>.structure.json` file state how the
documents its name governs are laid out: how many H1 titles they hold, which H2 sections in which order, and
which sections must hold content or must not appear. An order over a sequence of any length cannot be said in
JSON Schema, which is why the file is a dialect of its own. `lorecraft check structure` applies these keys.

## Table of Contents

1. [Key Concepts](#key-concepts)
2. [Configuration](#configuration)
3. [Usage](#usage)
4. [Limitations](#limitations)
5. [References](#references)
6. [Code References](#code-references)

## Key Concepts

- **Section**: An H2 heading and everything under it up to the next H2, its H3 subsections included.
- **Outline**: The order of a document's sections, matched left to right.
- **Named entry**: An outline entry naming one section, which a document must hold unless the entry is
  optional.
- **`any` run**: An outline entry matching any number of sections the outline does not name. The run stops at
  a named section, wherever that section's entry sits.

## Configuration

| Key | Value | Meaning |
|-----|-------|---------|
| `title` | `{"count": <n>, "first": <bool>}` | How many H1 titles a document holds, and whether one comes before any section |
| `empty_sections` | `"forbidden"` | Every heading must have content under it |
| `outline` | list of entries | `{"section": "<name>"}`, with `"optional": true` when it may be left out, or `{"any": true}` |
| `forbidden` | list of names | Sections that must not appear anywhere |

Every key is optional. An outline entry may also cap its section's words, as
[spec-structure-budget](spec-structure-budget.md) describes.

A named entry may carry two more optional keys, which `any` entries never take:

| Entry key | Value | Meaning |
|-----------|-------|---------|
| `description` | text | What the section holds |
| `examples` | non-empty list of Markdown | Samples of the section's body, each without its heading, none empty |

They change no rule. When a required section is absent, the finding carries the description and the first
example as notes, as [cli-check-structure](cli-check-structure.md#usage) shows. The other examples serve a reader
of the specification, as JSON Schema's `examples` do.

## Usage

### A Corpus Outline

Sections a document names for itself come first, then a required `Checklist`, then an optional `References`,
and nothing after it:

```json
{
  "$schema": "../schemas/structure.spec.json",
  "title": { "count": 1, "first": true },
  "empty_sections": "forbidden",
  "outline": [
    { "any": true },
    { "section": "Checklist" },
    { "section": "References", "optional": true }
  ],
  "forbidden": ["Changelog"]
}
```

### Describing a Section

A required section can say what it holds and show samples, so a writer who omitted it learns what to add.
Here the samples are trimmed from the `Checklist` of `docs/code/logging.md` and of `docs/code/python-docstrings.md`:

```json
{
  "$schema": "../schemas/structure.spec.json",
  "outline": [
    { "any": true },
    {
      "section": "Checklist",
      "description": "A verification list of items the author ticks before committing, each one a checkable statement of a rule in the document.",
      "examples": [
        "Before committing code, verify:\n\n- [ ] Every module that logs has exactly one `logger = logging.getLogger(__name__)` after its imports\n- [ ] No logger is stored as `self.logger` or any other instance or class attribute\n- [ ] No log call sits in a per-line loop, whatever its level",
        "Before committing code, verify:\n\n- [ ] Every new class and public function has a docstring whose first line is a one-line summary\n- [ ] No `Returns:` section restates the return annotation\n- [ ] A generator documents `Yields:`, never `Returns:`"
      ]
    }
  ]
}
```

### A Namespace Outline

A namespace outline is matched on its own, beside the corpus outline. Here it makes `Configuration` required,
and leaves where it sits to the corpus outline by surrounding it with `any` runs:

```json
{
  "$schema": "../schemas/structure.spec.json",
  "outline": [
    { "any": true },
    { "section": "Configuration" },
    { "any": true }
  ]
}
```

### Refused on Load

Beyond what [spec-structure](spec-structure.md#refused-on-load) refuses for any file, these keys are refused
when `title` sets a `count` below `1`, when the outline names a section twice or places two `any` runs side by
side, or when `forbidden` names a section the outline names.

## Limitations

- The outline names H2 sections only; H3 subsections are never required, ordered or forbidden.
- A section is matched on its exact heading text, without its `#` markers or inline markup.

## References

- [spec-structure](spec-structure.md) - Base: the file these keys belong to, its layers and its editor schema
- [spec-structure-budget](spec-structure-budget.md) - Related: the word cap an outline entry may carry
- [cli-check-structure](cli-check-structure.md) - Related: the check that applies the outline

## Code References

- `src/lorecraft/project/schemas/structure_file.py` - The shape of the outline keys
- `src/lorecraft/core/num.py` - The non-zero unsigned integer the title `count` holds, which refuses a value below `1`
- `src/lorecraft/project/schemas/structure.py` - Turns the keys into rules, and refuses an unusable outline
- `src/lorecraft/checks/structure.py` - Applies the title, outline, empty and forbidden rules to a document
