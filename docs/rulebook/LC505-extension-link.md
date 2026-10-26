---
name: "LC505-extension-link"
description: "A document links to a document that extends it"
code: "LC505"
since: "0.4.0"
---

# extension-link (LC505)

A document links to a document that extends it.

## What it does

Checks for links and images in a document whose target lies in the same directory and whose filename continues
the document's own name after a hyphen: `cli.md` linking to `cli-check.md`, or `feat.md` to `feat-cli.md`. The
check reads every corpus and every spec of `docs/__meta__/`. No spec key states the rule:
every document of a corpus that states a structure file, and every spec, is held to it.

A document whose name is continued by another is that document's base, and the other is its extension. The
extension names its base; the base never links to what extends it. Only a link to an existing file is
reported, as a link to nothing is `LC503`'s. A URL with a scheme, an absolute link and a fragment-only link
spell no relative path, so none of them is reported.

## Why is this bad?

A base is read on its own and stands for every extension that continues it. A link from the base to one of them
makes the base depend on a document that depends on it, so the base grows with each extension added and a
reader of the base is led into a specialisation they may not need.

## Example

`docs/feat/cli.md`:

```markdown
# CLI

The checks live in [the check command](cli-check.md).
```

## Use instead

Let the extension name its base, and leave the base without the link:

```markdown
# CLI

Each command has a document of its own.
```
