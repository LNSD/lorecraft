---
name: "skills"
description: "Writing rules for every agent skill in the repository. Load when creating or editing a SKILL.md"
type: "meta"
scope: "global"
---

# Agent Skill Format

**Applies to each discovered skill's `SKILL.md` entry.** Its structure file permits a task-shaped outline, forbids
empty sections and sets the whole-entry budget; the Agent Skills specification remains the frontmatter and link floor.

## Scope and Layers

The skill name is the directory name listed by an agent. The root `skills` layer governs every discovered entry;
`skills-<namespace>` layers govern a name equal to the namespace or beginning with `<namespace>-`, broad to narrow.
Each namespace adds rules to this one. Its structure file may tighten the token budget, and cannot widen the base.

Only the top-level `SKILL.md` is governed here. Resource files remain outside this corpus, including Markdown files;
their existing link checks still apply. A rule that applies to every skill belongs here, while a rule shared only by
a naming group belongs in its namespace layer.

## Content

Write the body for the agent that activates the skill: give it the steps, decisions and edge cases it needs to finish
the named task. Organize those instructions around the workflow rather than a prescribed section outline; skills
serve different tasks, so the checker accepts their own headings. Keep the entry focused, and move material used only
occasionally to a linked reference file.

Do not copy the Agent Skills specification's frontmatter or link rules here. The built-in schema and skill checks
already decide those requirements. This corpus adds only repository conventions and does not govern other files in a
skill directory.

## Checklist

- [ ] The entry gives useful instructions for the task named in its description
- [ ] Each heading introduces content; remove empty headings
- [ ] The entry stays within its whole-file budget, including frontmatter and examples
- [ ] Repository rules do not repeat a built-in Agent Skills requirement
- [ ] Namespace-specific instructions apply to a real group of skill names

## References

- [meta](meta.md) - Extends: Base meta corpus specification
