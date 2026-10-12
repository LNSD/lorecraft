---
name: "LC016-unreadable-skill-entry"
description: "A skill entry cannot be resolved or listed"
code: "LC016"
since: "0.3.0"
---

# unreadable-skill-entry (LC016)

A skill entry cannot be resolved or listed.

## What it does

Checks for skill entries, the directories or links directly inside a skills directory, that the operating system
refuses to resolve, inspect or list, such as one whose permissions deny it, or a link that cannot be followed.
It is reported once, at its path, and nothing under it is loaded. Every other corpus, skill and document is
checked as if it could be read.

`lorecraft check` reads the whole repository before it reports anything, and a refusal at that point stops the run
with an error naming the path and exit status 2, so it does not report this code today: it is reported only where
the workspace is read without that first read.

It has no level, so no configuration turns it off, and it is always reported as an error.

## Why is this bad?

Until the skill entry can be reached, nothing under it is checked, so a violation there goes unreported and an
agent loads it unreviewed.

## Example

`.agents/skills/review/`, with its permissions removed:

```console
$ chmod 000 .agents/skills/review
```

## Use instead

Give the directory its permissions back:

```console
$ chmod 755 .agents/skills/review
```
