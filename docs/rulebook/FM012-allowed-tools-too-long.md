---
name: "FM012-allowed-tools-too-long"
description: "A skill's `allowed-tools` value exceeds the recommended length"
code: "FM012"
since: "0.3.0"
---

# allowed-tools-too-long (FM012)

A skill's `allowed-tools` value exceeds the recommended length.

## What it does

Checks for skills whose whole `allowed-tools` value exceeds 500 characters, including whitespace and
parenthesised patterns. Exactly 500 characters is within the recommendation. Characters count, not bytes.
This is Lorecraft's recommendation, matching the Agent Skills specification's limit for `compatibility`;
that specification sets no length limit for `allowed-tools`. No repository meta spec changes it.

## Why is this bad?

A long list of pre-approved tools hides which permissions the skill really needs: an agent running the skill holds
every tool the list approves, so each unnecessary or overlapping entry widens what it may do without asking.

## Example

`.agents/skills/review/SKILL.md`, with more than 500 characters in `allowed-tools`:

```markdown
---
name: review
description: Review a change.
allowed-tools: >-
  Read Grep Bash(git diff *) Bash(git log *)
  # ... many more tool entries
---
```

## Use instead

Keep only the permissions the skill needs:

```markdown
---
name: review
description: Review a change.
allowed-tools: Read Grep Bash(git diff *)
---
```
