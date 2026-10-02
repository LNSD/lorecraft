---
name: "spec-structure-budget"
description: "The length keys of a structure specification: the words cap on an outline entry and what counts as a prose word, the whole-file tokens budget in o200k_base tokens, and how a namespace file tightens either. Load when setting or changing a word cap or a token budget, or asking why a section or a document is reported over its limit"
type: "feature"
status: "experimental"
components: "module:lorecraft.project,module:lorecraft.checks,spec:feat,spec:code"
---

# Word Caps and Token Budget

## Summary

A `<stem>.structure.json` file limits the length of the documents its stem governs in two ways. A `words` cap
on an outline entry keeps a section's prose concise for the person reading it, and the `tokens` key budgets the
whole file, which is what loading the document costs an agent. `lorecraft check structure` applies the caps and
`lorecraft check budget` the budget.

## Table of Contents

1. [Key Concepts](#key-concepts)
2. [Configuration](#configuration)
3. [Usage](#usage)
4. [Limitations](#limitations)
5. [References](#references)
6. [Code References](#code-references)

## Key Concepts

- **Word cap**: The most prose words a section may hold, its H3 subsections included.
- **Prose word**: Whitespace-delimited text outside code blocks, fenced or indented, table rows and headings, so
  an example, a reference table or a heading costs no words.
- **Token budget**: The most `o200k_base` tokens the whole file may hold, frontmatter, code and tables
  included. The count is the same whichever agent reads the document.

## Configuration

| Key | Where | Value | Meaning |
|-----|-------|-------|---------|
| `words` | an `outline` entry | integer | The word cap of the section the entry names; on an `any` entry, of each section in the run alone |
| `tokens` | top level | integer | The token budget of the whole file |

Both are optional: an entry without `words` caps nothing, and a file without `tokens` sets no budget. The
outline entries a cap sits on are the ones [spec-structure-outline](spec-structure-outline.md) describes.

## Usage

### Caps and a Budget

```json
{
  "$schema": "../schemas/structure.spec.json",
  "tokens": 5000,
  "outline": [
    { "any": true, "words": 350 },
    { "section": "Checklist", "words": 250 },
    { "section": "References", "optional": true }
  ]
}
```

Each section a document names for itself holds at most 350 words, `Checklist` at most 250, and `References`
is not capped. The whole file holds at most 5000 tokens.

### Tightening in a Namespace

Each file is applied on its own, so a document must fit the caps and the budget of every file that governs it.
A namespace file can therefore tighten a cap or the budget, and cannot raise either:

```json
{
  "$schema": "../schemas/structure.spec.json",
  "tokens": 3000,
  "outline": [
    { "any": true },
    { "section": "Configuration", "words": 150 },
    { "any": true }
  ]
}
```

### Refused on Load

Beyond what [spec-structure](spec-structure.md#refused-on-load) refuses for any file, a `words` or `tokens`
value below `1` is refused.

## Limitations

- A cap is set on a section; no key caps an H3 subsection on its own, the total of an `any` run, or the prose
  of a whole document.
- The budget counts `o200k_base` tokens whatever model reads the document; another tokenizer counts
  differently.

## References

- [spec-structure](spec-structure.md) - Base: the file these keys belong to, its layers and its editor schema
- [spec-structure-outline](spec-structure-outline.md) - Related: the outline entries a word cap is set on
- [cli-check-structure](cli-check-structure.md) - Related: the check that applies the word caps
- [cli-check-budget](cli-check-budget.md) - Related: the check that applies the token budget

## Code References

- `src/lorecraft/project/schemas/structure_file.py` - The shape of the `words` and `tokens` keys
- `src/lorecraft/project/schemas/structure.py` - Turns the keys into rules, and refuses a value below `1`
- `src/lorecraft/checks/structure.py` - Applies the word caps to a document's sections
- `src/lorecraft/checks/budget.py` - Applies the token budget to a document's token count
