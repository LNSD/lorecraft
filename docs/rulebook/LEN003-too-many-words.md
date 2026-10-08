---
name: "LEN003-too-many-words"
description: "A section is longer than its word cap allows"
code: "LEN003"
since: "0.3.0"
---

# too-many-words (LEN003)

A section is longer than its word cap allows.

## What it does

Checks for H2 sections longer than the `words` cap their structure specification sets in its `outline`: the
cap of the entry naming the section, or, for a section the outline does not name, the cap of the `any` run it
falls in. The cap covers the section's subsections too. Only prose counts: fenced code blocks, table rows and
headings do not.

A document that more than one specification governs, such as a corpus and a namespace, must keep each section
within every cap they set, and is reported once for each cap a section exceeds.

## Why is this bad?

A cap keeps a section to what an agent needs from it; every word past it costs the agent context on every load
and buries the rule it came for.

## Example

`docs/__meta__/guide.structure.json`:

```json
{
  "outline": [
    { "section": "Configuration", "words": 150 }
  ]
}
```

`docs/guide/setup.md`, with a `Configuration` section of 420 words:

```markdown
# Setup

## Configuration

Every option the configuration file accepts, with its default and the reasons to change it:

<!-- ... 400 more words, one paragraph per option -->
```

## Use instead

Keep what an agent needs on every load, and move the rest into a document of its own:

```markdown
# Setup

## Configuration

Every option the configuration file accepts is described in [configuration](configuration.md).
```
