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

## Full-message bodies

Keep each summary and bullet on one physical line. Do not hard-wrap the body; there is no body character
limit and GitHub wraps text to fit the display.

```
feat(lorewright): fail a malformed rule document at the parse boundary

A missing frontmatter key surfaces as a `KeyError` inside the first check
that reads it, so the report blames the check instead of the document.

- Parse frontmatter into a record up front, so each document is either
  well-formed or rejected before any check sees it
- Report the offending key and document path together, which tells the
  author what to fix
- Treat a `name` disagreeing with the filename stem as malformed, closing
  the way two documents could claim the same identity
```

```
docs(code): let a typing task load the typing rules alone

The annotation rules lived inside the module-layout document, so agents
that needed them also loaded unnecessary layout rules against a fixed
context budget.

- Give typing its own document, addressable on its own from `/code-rules`
- Narrow the module document to layout, imports and `__init__.py`
  contents, so neither document answers questions about the other
- Cross-link both, so arriving at either one still leads to the rule
  actually wanted
```

```
chore(deps): bump ruff floor to 0.16.0
```
