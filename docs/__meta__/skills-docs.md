---
name: "skills-docs"
description: "Additional writing rules for documentation workflow skills. Load when creating or editing a docs-* skill"
type: "meta"
scope: "global"
---

# Documentation Skill Layer

**Applies to documentation skills.** This layer extends [skills](skills.md) and sets a budget for their writing,
creation and review workflows.

## Documentation Workflows

Tell the agent how to find the governing documentation rules before it writes or reviews a document. Keep the
writing path, validation path and spec creation path distinct; route each to its corresponding skill when a
task crosses those boundaries. A skill may summarize a necessary step, but the repository's specs remain the
authority for document content.

The 3500-token limit keeps a documentation workflow focused while leaving room for examples and edge cases. It
applies in addition to the base budget.

## Checklist

- [ ] A documentation task resolves the governing specs before editing
- [ ] Creation and review workflows direct the agent to the right operation
- [ ] Document conventions link to their spec instead of competing with it

## References

- [skills](skills.md) - Extends: Base rules for every skill
