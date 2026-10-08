---
name: "LAY001-outside-symlink"
description: "A symlink an agent follows in the skill layout leads outside the repository"
code: "LAY001"
since: "0.3.0"
---

# outside-symlink (LAY001)

A symlink an agent follows in the skill layout leads outside the repository.

## What it does

Checks for symlinks an agent follows to load a skill whose chain leads outside the repository: a skills
directory, an entry in a skills directory, an entry's `SKILL.md`, or a file or directory inside a skill. The
chain leaves when any link on it does, the symlink itself or one it leads through, by an absolute target or by
a `..` that climbs above the repository's root. A symlink that leads elsewhere inside the repository does not
count, nor does one that dangles inside it. Nothing behind a symlink that leaves is read, so no other rule
judges what it leads to. The package states the rule; no specification sets or changes it.

## Why is this bad?

An agent loads whatever the symlink leads to, which the repository does not hold, so the skill loads
differently, or not at all, for everyone who checks the repository out somewhere else.

## Example

`.agents/skills/review`, linked to a directory in one user's home:

```console
$ ls -l .agents/skills
review -> /home/alex/skills/review
```

## Use instead

Keep the skill inside the repository, and link to it there:

```console
$ ls -l .agents/skills
review -> ../../skills/review
```
