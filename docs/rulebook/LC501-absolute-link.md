---
name: "LC501-absolute-link"
description: "A link in a Markdown file starts at a filesystem root"
code: "LC501"
since: "0.3.0"
---

# absolute-link (LC501)

A link in a Markdown file starts at a filesystem root.

## What it does

Checks for links and images whose destination starts with `/`, as written or once percent-decoded, so
`%2Fetc/x.md` is reported too, in every Markdown file the checks read: every document, a skill's `SKILL.md`
and each Markdown file inside the skill. No spec key states the rule: every such file is held to it.

A URL with a scheme, such as `https://example.com/setup`, does not start with `/`, and neither does a link to a
heading of the same file, such as `#usage`, so neither is reported.

## Why is this bad?

A path that starts with `/` is read from the root of the filesystem, or of the site that renders the file, never
from the repository, so the link breaks wherever the files are checked out or installed. An agent that follows
it reads a file the repository does not hold, or nothing.

## Example

`docs/guide/setup.md`:

```markdown
# Setup

Every option is listed in [the configuration](/docs/guide/configuration.md).
```

## Use instead

Spell the path relative to the file, as a document's links are read:

```markdown
# Setup

Every option is listed in [the configuration](configuration.md).
```
