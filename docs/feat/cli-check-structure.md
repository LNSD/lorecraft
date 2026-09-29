---
name: "cli-check-structure"
description: "lorecraft check structure: validating each document's H1 title, section order, empty and forbidden sections, and per-section word caps against the structure specifications its path selects, and the rule identifiers it reports. Load when a structure or word cap finding needs explaining, or when running the structure check on its own"
type: "feature"
status: "experimental"
components: "module:lorecraft.cli.commands.check.structure,module:lorecraft.checks.structure,module:lorecraft.project.schemas.structure,module:lorecraft.project.syntax,spec:feat,spec:code"
---

# `lorecraft check structure`

## Summary

`lorecraft check structure` validates the headings of each document against every structure specification,
`<stem>.structure.json`, that the document's path selects: the H1 title, the order of the sections, sections
left empty or forbidden, and the prose words each section holds. It is also one of the checks a bare
`lorecraft check` runs.

## Table of Contents

1. [Key Concepts](#key-concepts)
2. [Configuration](#configuration)
3. [Usage](#usage)
4. [Limitations](#limitations)
5. [Findings](#findings)
6. [References](#references)
7. [Code References](#code-references)

## Key Concepts

- **Section**: An H2 heading and everything under it up to the next H2, its H3 subsections included.
- **Structure specification**: A `<stem>.structure.json` file stating the outline, as
  [spec-structure-outline](spec-structure-outline.md) describes, and the word caps, as
  [spec-structure-budget](spec-structure-budget.md) describes.
- **Word cap**: The most prose words a section may hold. Prose excludes fenced code blocks and table rows.
- **Layer**: Each structure specification that applies to a document; every one is applied on its own, so a
  document must pass the corpus specification and each namespace specification alike.

## Configuration

| Argument or option | Default | Description |
|--------------------|---------|-------------|
| `PATHS...`         | every document | The documents to check, relative to the working directory, as [Document Selection](cli-check.md#document-selection) describes |
| `--root <path>`    | nearest parent holding `docs/__meta__/` | The repository root, as [cli-check](cli-check.md#root-discovery) describes |
| `--format <text\|json>` | `text` | The output format, as [cli-check](cli-check.md#output) describes |

## Usage

```bash
# Check the structure of every document
lorecraft check structure

# Check one document just written
lorecraft check structure docs/feat/cli-check-structure.md
```

```text
docs/feat/spec-demo.md:15: [structure.empty] section `Key Concepts` is empty; omit it rather than leaving it empty (per feat.md)
docs/feat/spec-demo.md:15: [structure.outline] expected section `Table of Contents`, found `Key Concepts` (per feat.md)
checked 1 file(s), 2 finding(s)
```

Every message ends by naming the prose specification the rule comes from, such as `(per feat.md)`, so a
reader is sent to the rule rather than to the JSON. The output and the exit status are the ones every check
shares: see [Output](cli-check.md#output) and [Exit Status](cli-check.md#exit-status). A document in a corpus
with no structure specification is listed as `<corpus>.ungoverned` with the reason `no structure spec for this
corpus; structure unvalidated`.

## Limitations

- The outline is matched on H2 headings only; H3 subsections are counted in their section's words but never
  required, ordered or forbidden.
- The outline reports its first divergence and stops, since every later section would be measured against an
  entry it was never meant to match. Fix it and run again to see the next.
- The `tokens` budget a structure specification may set is not read here; `lorecraft check budget` applies it.

## Findings

| Rule | Reported when |
|------|---------------|
| `structure.title` | The document has a different number of H1 titles than the specification requires, or a required H1 does not come first |
| `structure.empty` | A heading has no content under it, where empty sections are forbidden |
| `structure.forbidden` | A section the specification forbids appears |
| `structure.outline` | A required section is missing, a section is out of order, or a section follows where the outline ends |
| `structure.words.section` | A section holds more prose words than its cap |
| `structure.undecodable` | The file is not valid UTF-8 |

## References

- [cli-check](cli-check.md) - Base: root discovery, document selection, output and exit status
- [spec-structure-outline](spec-structure-outline.md) - Dependency: the outline keys this check reads
- [spec-structure-budget](spec-structure-budget.md) - Dependency: the `words` caps this check reads
- [cli-check-budget](cli-check-budget.md) - Related: the whole-file token budget from the same specification

## Code References

- `src/lorecraft/cli/commands/check/structure.py` - Declares the command and registers the check with the group
- `src/lorecraft/checks/structure.py` - The check of one document's headings
- `src/lorecraft/project/schemas/structure.py` - Loads and validates a structure specification
