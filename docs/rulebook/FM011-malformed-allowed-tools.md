---
name: "FM011-malformed-allowed-tools"
description: "A skill's `allowed-tools` is not a list of tool entries"
code: "FM011"
since: "0.3.0"
---

# malformed-allowed-tools (FM011)

A skill's `allowed-tools` is not a list of tool entries.

## What it does

Checks for skills whose `allowed-tools` entries do not match the list structure adopted for the Agent Skills
specification's experimental field: a tool name of ASCII letters, digits, underscores or hyphens, optionally
followed by one balanced parenthesised pattern. Spaces and commas inside that pattern belong to it. Whether a
particular agent recognises a tool or its pattern syntax is not checked.

## Why is this bad?

A malformed entry may be read as a different set of pre-approved tools than the skill author intended.

## Example

```markdown
---
name: review
description: Review a change.
allowed-tools: Read, Grep
---
```

## Use instead

Separate entries with whitespace:

```markdown
---
name: review
description: Review a change.
allowed-tools: Read Grep
---
```
