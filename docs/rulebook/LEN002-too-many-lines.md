---
name: "LEN002-too-many-lines"
description: "A skill's `SKILL.md` is longer than the Agent Skills specification allows"
code: "LEN002"
since: "0.3.0"
---

# too-many-lines (LEN002)

A skill's `SKILL.md` is longer than the Agent Skills specification allows.

## What it does

Checks for skills whose `SKILL.md` holds more than 500 lines, the budget the Agent Skills specification sets.
The whole file counts: frontmatter, blank lines and code blocks as much as prose. A file of exactly 500 lines
is within the budget. No specification in the repository sets or changes it.

## Why is this bad?

An agent loads the whole `SKILL.md` every time the skill activates, so every line of it is spent on every
activation, whether that activation needs it or not.

## Example

`.agents/skills/review/SKILL.md`, at 612 lines:

```markdown
---
name: review
description: Review a change before it is merged.
---

# Review

Read the diff, then walk the checklist below.

## Checklist

<!-- ... 601 more lines, one subsection per kind of change -->
```

## Use instead

Move what most activations do not need into a file under `references/`, and say when to read it:

```markdown
---
name: review
description: Review a change before it is merged.
---

# Review

Read the diff, then walk the checklist below.

## Checklist

Read [the checklist](references/checklist.md) for the kind of change under review.
```
