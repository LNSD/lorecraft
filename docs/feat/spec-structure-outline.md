---
name: "spec-structure-outline"
description: "The outline keys of a structure file: the one H1 title every governed document carries and the word and character caps and the pattern a title key sets on it, the outline of H2 sections with required, optional and any entries, empty_sections and forbidden sections, how a namespace outline adds to the corpus outline, and which outlines are refused on load. Load when writing or changing a section outline, requiring, ordering or forbidding a section, or an outline is reported invalid"
type: "feature"
status: "experimental"
components: "module:lorecraft.project,module:lorecraft.checks,spec:feat,spec:code"
---

# Section Outline Rules

## Summary

The `outline`, `empty_sections` and `forbidden` keys of a `<name>.structure.json` file state which H2 sections
the documents its name governs hold, in which order, and which must hold content or not appear. Every governed
document carries exactly one H1 title that opens it; `title` caps its length or sets its pattern. An order over a
sequence of any length is no JSON Schema, so the file is a dialect of its own. `lorecraft check` applies them.

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
| `title` | `{"words": N}`, `{"chars": N}`, `{"pattern": "<regex>"}`, or several | The title's text holds at most `N` words, at most `N` characters, and matches the pattern |
| `empty_sections` | `"forbidden"` | Every heading must have content under it |
| `outline` | list of entries | `{"section": "<name>"}`, with `"optional": true` when it may be left out, or `{"any": true}` |
| `forbidden` | list of names | Sections that must not appear anywhere |

Every key is optional. An outline entry may also cap its section's words, as
[spec-structure-budget](spec-structure-budget.md) describes.

The `title` key's `words` and `chars` are positive integers. `words` counts prose words, each whitespace-delimited
token of the H1's text; `chars` counts the code points of that text, without its `#` marker or inline markup. Only
the first H1 is measured, and a document with no title is reported as missing one, never as over a cap. A title
over a cap is `LEN004 title-too-many-words` or `LEN005 title-too-long`, at its heading, once per meta spec
that sets it: a corpus and a namespace cap each apply on their own.

Its `pattern` is a Python `re` expression that the title's text must match. It is matched as
JSON Schema's `pattern` is, searched for anywhere in the text, so `^[A-Z]` asks only for a capital first letter, and a
pattern that must hold the whole title anchors itself with `^` and `$`. Only the first H1 is matched, and a document
with no title is reported as missing one alone. A title that does not match is `OUT009 invalid-title`, at its
heading, once per meta spec that sets a pattern. Each key may be set alone, and each applies on its own: the
two caps are upper bounds and never conflict, but a `pattern` that only titles longer than a cap can match, such as
`{"chars": 40, "pattern": "^.{60,}$"}`, fails every governed document, and is not refused on load.

A named entry may carry two more optional keys, which `any` entries never take:

| Entry key | Value | Meaning |
|-----------|-------|---------|
| `description` | text | What the section holds |
| `examples` | non-empty list of Markdown | Samples of the section's body, each without its heading, none empty |

They change no rule. When a required section is absent, the diagnostic carries the description and the first
example as a help and a note, as [cli-check](cli-check.md#output) describes. The other examples serve a reader
of the meta spec, as JSON Schema's `examples` do.

## Usage

### A Corpus Outline

Sections a document names for itself come first, then a required `Checklist`, then an optional `References`,
and nothing after it:

```json
{
  "$schema": "../schemas/structure.spec.json",
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
when the outline names a section twice or places two `any` runs side by side, or when `forbidden` names a section
twice or one the outline names. A `title` stating no check, `{}`, is refused, since it would check nothing, and so
is an empty `pattern`, which every title matches. A `pattern` that does not compile is refused with an error naming
the file and the pattern. A section name, in the outline or in `forbidden`, is refused when it is empty, has
whitespace at either end, or spans two lines: no heading's text could match it.

## Limitations

- The outline names H2 sections only; H3 subsections are never required, ordered or forbidden.
- A section is matched on its exact heading text, without its `#` markers or inline markup.

## References

- [spec-structure](spec-structure.md) - Base: the file these keys belong to, its layers and its editor schema
- [spec-structure-budget](spec-structure-budget.md) - Related: the word cap an outline entry may carry
- [cli-check](cli-check.md) - Related: the command that applies the outline

## Code References

- `src/lorecraft/project/schemas/structure_file.py` - The shape of the outline keys
- `src/lorecraft/project/schemas/section_name.py` - The section name an outline entry and `forbidden` hold
- `src/lorecraft/project/schemas/structure.py` - Turns the keys into rules, and refuses an unusable outline
- `src/lorecraft/rules/outline/` - The `OUT` rules that apply the title, outline, empty and forbidden keys
- `src/lorecraft/rules/length/title_too_many_words.py` - Reports a title over its word cap as `LEN004`
- `src/lorecraft/rules/length/title_too_long.py` - Reports a title over its character cap as `LEN005`
- `src/lorecraft/rules/outline/invalid_title.py` - Reports a title failing its pattern as `OUT009`
