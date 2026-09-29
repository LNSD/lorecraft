---
name: "cli-check-header"
description: "lorecraft check header: validating each document's YAML frontmatter against the frontmatter schemas of the structure specifications its path selects, the name-matches-filename rule, and the rule identifiers it reports. Load when a frontmatter finding needs explaining, or when running the header check on its own"
type: "feature"
status: "experimental"
components: "module:lorecraft.cli.commands.check.header,module:lorecraft.checks.header,module:lorecraft.project.schemas.structure,spec:feat,spec:code"
---

# `lorecraft check header`

## Summary

`lorecraft check header` validates the YAML frontmatter at the top of each document against the
`frontmatter` key of every structure specification, `<stem>.structure.json`, that the document's path selects,
and checks that the frontmatter `name` equals the filename. It is also one of the checks a bare
`lorecraft check` runs.

## Table of Contents

1. [Key Concepts](#key-concepts)
2. [Configuration](#configuration)
3. [Usage](#usage)
4. [Findings](#findings)
5. [References](#references)
6. [Code References](#code-references)

## Key Concepts

- **Frontmatter**: The YAML mapping between two `---` lines that opens a document.
- **Frontmatter schema**: The `frontmatter` key of a `<stem>.structure.json` file; a JSON Schema the
  frontmatter must satisfy, as [spec-header](spec-header.md) describes.
- **Layer**: Each frontmatter schema that applies to a document; every one is applied on its own, so a
  document governed by a corpus schema and a namespace schema must satisfy both.

## Configuration

| Argument or option | Default | Description |
|--------------------|---------|-------------|
| `PATHS...`         | every document | The documents to check, relative to the working directory, as [Document Selection](cli-check.md#document-selection) describes |
| `--root <path>`    | nearest parent holding `docs/__meta__/` | The repository root, as [cli-check](cli-check.md#root-discovery) describes |
| `--format <text\|json>` | `text` | The output format, as [cli-check](cli-check.md#output) describes |

## Usage

```bash
# Check the frontmatter of every document
lorecraft check header

# Check one document just written
lorecraft check header docs/feat/cli-check-header.md
```

```text
docs/feat/spec-demo.md:3: [feat.description] 'A demo' does not match 'Load when' (per docs/__meta__/feat.structure.json)
checked 1 file(s), 1 finding(s)
```

The output and the exit status are the ones every check shares: see [Output](cli-check.md#output) and
[Exit Status](cli-check.md#exit-status). A document whose corpus structure specification has no `frontmatter`
key is listed as `<corpus>.ungoverned` with the reason
`no frontmatter schema for this corpus; frontmatter unvalidated`, whatever a namespace specification states.

## Findings

A finding is reported on the line of the key it concerns, or on line 1 when the key is absent or the whole
block is at fault. A document whose frontmatter is missing, unparseable or undecodable reports that one
finding and nothing else.

| Rule | Reported when |
|------|---------------|
| `frontmatter.missing` | The document does not open with a `---` delimited block |
| `frontmatter.unparseable` | The block is not valid YAML, or is not a mapping |
| `frontmatter.undecodable` | The file is not valid UTF-8 |
| `frontmatter.name-matches-filename` | `name` is not the filename without `.md` |
| `<corpus>.<field>` | A frontmatter schema rejects that field, or requires it and it is absent; the message names the specification |
| `<corpus>.frontmatter` | A frontmatter schema rejects the frontmatter as a whole, such as a key it does not allow |

The `<corpus>` prefix is the document's corpus, whichever layer's schema the finding comes from.

## References

- [cli-check](cli-check.md) - Base: root discovery, document selection, output and exit status
- [spec-header](spec-header.md) - Dependency: the frontmatter schema this check reads

## Code References

- `src/lorecraft/cli/commands/check/header.py` - Declares the command and registers the check with the group
- `src/lorecraft/checks/header.py` - The check of one document's frontmatter
- `src/lorecraft/project/schemas/structure.py` - Loads and validates the frontmatter schema with the rest of the
  structure specification
