---
name: "cli-check-budget"
description: "lorecraft check budget: counting each document's whole-file o200k_base tokens against the tokens budget its structure specifications set, and the rule identifiers it reports. Load when a document is reported over its token budget, or when running the budget check on its own"
type: "feature"
status: "experimental"
components: "module:lorecraft.cli.commands.check.budget,module:lorecraft.checks.budget,module:lorecraft.project.syntax.tokens,spec:feat,spec:code"
---

# `lorecraft check budget`

## Summary

`lorecraft check budget` counts the tokens in each document's whole file and compares the count with the
`tokens` budget of every structure specification that applies to the document. The count is what loading the
document costs an agent, so it includes the frontmatter, code blocks and tables that word caps leave out. It is
also one of the checks a bare `lorecraft check` runs.

## Table of Contents

1. [Key Concepts](#key-concepts)
2. [Configuration](#configuration)
3. [Usage](#usage)
4. [Limitations](#limitations)
5. [Findings](#findings)
6. [References](#references)
7. [Code References](#code-references)

## Key Concepts

- **Token budget**: The most tokens a whole document file may hold, set by the `tokens` key of a
  `<stem>.structure.json` file, as [spec-structure](spec-structure.md) describes.
- **Token count**: The number of OpenAI `o200k_base` tokens in the file's text. It is the same whichever agent
  reads the document, and needs no network access.
- **Governed**: A document is governed by this check only when one of its structure specifications sets a
  `tokens` budget; one whose specifications set none is ungoverned.

## Configuration

| Argument or option | Default | Description |
|--------------------|---------|-------------|
| `PATHS...`         | every document | The documents to check, relative to the working directory, as [Document Selection](cli-check.md#document-selection) describes |
| `--root <path>`    | nearest parent holding `docs/__meta__/` | The repository root, as [cli-check](cli-check.md#root-discovery) describes |
| `--format <text\|json>` | `text` | The output format, as [cli-check](cli-check.md#output) describes |

## Usage

```bash
# Check the token budget of every document
lorecraft check budget

# Check one document just written
lorecraft check budget docs/feat/cli-check-budget.md
```

A document over budget reports one finding on line 1 for each specification whose budget it exceeds, naming
the count, the budget and the specification file. With a `feat` budget of 100:

```text
docs/feat/cli-check-budget.md:1: [budget.tokens] 1001 tokens; the budget is 100 (per feat.structure.json)
checked 1 file(s), 1 finding(s)
```

The output and the exit status are the ones every check shares: see [Output](cli-check.md#output) and
[Exit Status](cli-check.md#exit-status). An ungoverned document is listed as `<corpus>.ungoverned` with the
reason `no token budget for this corpus; tokens unvalidated`.

## Limitations

- The count is `o200k_base` whatever model will read the document; another tokenizer counts differently.
- Each budget is applied on its own, so a namespace specification can tighten the corpus budget but not raise
  it.

## Findings

| Rule | Reported when |
|------|---------------|
| `budget.tokens` | The file holds more tokens than a specification's budget; one finding per such specification |
| `budget.undecodable` | The file is not valid UTF-8 |

## References

- [cli-check](cli-check.md) - Base: root discovery, document selection, output and exit status
- [spec-structure](spec-structure.md) - Dependency: the `tokens` key this check reads
- [cli-check-structure](cli-check-structure.md) - Related: the per-section word caps from the same specification

## Code References

- `src/lorecraft/cli/commands/check/budget.py` - Declares the command and registers the check with the group
- `src/lorecraft/checks/budget.py` - The check of one document's token count
- `src/lorecraft/project/syntax/tokens.py` - Counts tokens, with the vocabulary shipped in the package
