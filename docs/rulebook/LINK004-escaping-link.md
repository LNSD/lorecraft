---
name: "LINK004-escaping-link"
description: "A relative link in a skill's file climbs above the skill root"
code: "LINK004"
since: "0.3.0"
---

# escaping-link (LINK004)

A relative link in a skill's file climbs above the skill root.

## What it does

Checks for relative links and images in a skill's `SKILL.md` and in each Markdown file inside the skill whose
path, read from the skill root, leads above it. The Agent Skills specification has every file of a skill name
another by its path from the skill root, wherever the file lies: in `references/guide.md`, `SKILL.md` names the
skill's own `SKILL.md`, and `../SKILL.md` leads out of the skill. No specification key states the rule: every
skill is held to it.

The path alone decides, never where the skill lies in the repository: `../../skills/review/SKILL.md` leaves the
skill even when it leads back into it. A path that climbs and comes back down inside the skill, such as
`references/../SKILL.md`, stays inside. A URL with a scheme, an absolute link and a link to a heading of the same
file spell no relative path, so none of them is reported. A document is never judged: its links are read from
its own directory, and may climb out of it.

## Why is this bad?

A skill is installed on its own, wherever an agent keeps its skills, and carries only its own files. A link
above the skill root points at a file the installed skill does not carry, so an agent that follows it reads
nothing, or a file that happens to lie there.

## Example

`.agents/skills/review/references/checklist.md`:

```markdown
# Checklist

Start from [the review steps](../SKILL.md).
```

## Use instead

Name the file by its path from the skill root:

```markdown
# Checklist

Start from [the review steps](SKILL.md).
```
