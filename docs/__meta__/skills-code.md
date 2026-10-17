---
name: "skills-code"
description: "Additional writing rules for code workflow skills. Load when creating or editing a code-* skill entry"
type: "meta"
scope: "global"
---

# Code Skill Layer

**Applies to code skills.** This layer extends [skills](skills.md) and tightens the entry budget for command and
review workflows.

## Code Workflows

State when the workflow applies and what outcome it produces. For a command-driven skill, show the commands in the
order an agent runs them and distinguish checks that inspect from commands that modify files. State relevant
preconditions and failure outcomes where the agent must choose what to do next. Keep general coding conventions in
`docs/code/`; a skill may route to those rules but should not reproduce them.

Explain a check's scope and its result before offering repair commands. When a command changes files, make the
effect clear and leave a verification step after it. A skill for one operation should not become a general coding
index: send the agent to a sibling skill for a separate task.

The 6500-token limit leaves room for the longest current `code-*` entry, `code-test`, while keeping the namespace's
workflows focused. It applies in addition to the base budget.

## Checklist

- [ ] A code workflow identifies its trigger and intended outcome
- [ ] Commands appear in execution order, with modifying commands made clear
- [ ] Shared code conventions link to their code rules instead of copying them

## References

- [skills](skills.md) - Extends: Base rules for every skill entry
