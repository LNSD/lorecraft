---
name: "LEN001-too-many-tokens"
description: "A document is longer than its token budget allows"
code: "LEN001"
since: "0.3.0"
---

# too-many-tokens (LEN001)

A document is longer than its token budget allows.

## What it does

Checks for documents longer than the token budget their structure specification sets with its `tokens` key.
The whole file counts: frontmatter, code blocks and tables as much as prose.

A document that more than one specification governs, such as a corpus and a namespace, must fit every budget
they set, and is reported once for each budget it exceeds.

## Why is this bad?

An agent loads the whole document into its context, so every token of it is one less for the task at hand, on
every load.

## Example

`docs/__meta__/guide.structure.json`:

```json
{
  "tokens": 4000
}
```

`docs/guide/setup.md`, at 5200 tokens:

```markdown
# Setup

Install the toolkit, then run it once over the repository.

## Configuration

Every option the configuration file accepts, with its default and an example:

<!-- ... 1800 more tokens, one subsection per option -->
```

## Use instead

Move what an agent needs only some of the time into a document of its own, and link to it:

```markdown
# Setup

Install the toolkit, then run it once over the repository.

## Configuration

Every option the configuration file accepts is described in [configuration](configuration.md).
```
