# More before-and-after titles

Overflow from [SKILL.md](../SKILL.md) section *Before and After*. Same distinction throughout: the
*before* title names what was edited, the *after* title names what changed for the project.

**A pattern document's structure specification and schema landed under `docs/__meta__/`.**

| | |
|---|---|
| Before | `docs(meta): add code-pattern.structure.json and code-pattern.header.json` |
| After | `docs(meta): make a pattern document fail a check instead of a reviewer` |

The first lists two filenames. The second says what moved out of human review and into a gate, which is
the whole reason a format specification exists.

**A script that validates skills against the Agent Skills specification.**

| | |
|---|---|
| Before | `feat(skills): add check_skill.py with frontmatter and link validation` |
| After | `feat(skills): reject a skill the specification would not load` |

The first describes a file and its functions. The second names the class of breakage that can no longer
reach `main`.
