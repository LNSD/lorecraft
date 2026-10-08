---
name: "LINK003-broken-link"
description: "A relative link names nothing the repository holds"
code: "LINK003"
since: "0.3.0"
---

# broken-link (LINK003)

A relative link names nothing the repository holds.

## What it does

Checks for links and images whose relative path leads to nothing, in every Markdown file the checks read: a
document whose corpus states a structure specification, a skill's `SKILL.md` and each Markdown file inside the
skill. A path names a file or a directory, and any symlink on the way to it is followed. No specification key
states the rule: every such file is held to it.

Where the path is read from depends on the file. In a document, it is read from the document's own directory,
as Markdown renders it. In a skill, it is read from the skill root, whichever file of the skill holds the link,
as the Agent Skills specification has it: a link in `references/guide.md` to `SKILL.md` is `SKILL.md`.

A fragment or a query after the path is ignored, and a `..` cancels the directory written before it. A URL with
a scheme, an absolute link and a fragment-only link name no relative path, so they are not reported. Neither is
a link in a skill that climbs above the skill root, which `LINK004` reports, nor one in a document that climbs
above the repository, nor one leading into a directory the checks do not read, such as `../src/main.py` from a
document: whether it names something cannot be told.

## Why is this bad?

A link to nothing goes nowhere: an agent that follows it finds no file, and reads nothing of what the link
promised, or guesses at it.

## Example

`docs/guide/setup.md`, beside which no `install.md` exists:

```markdown
# Setup

Run the steps in [install](install.md) first.
```

## Use instead

Name a file that is there:

```markdown
# Setup

Run the steps in [installation](installation.md) first.
```
