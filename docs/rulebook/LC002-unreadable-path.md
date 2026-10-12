---
name: "LC002-unreadable-path"
description: "A path cannot be read"
code: "LC002"
since: "0.3.0"
---

# unreadable-path (LC002)

A path cannot be read.

## What it does

Checks for paths the operating system refuses to let the check read, list or look up, such as a structure file,
the `<name>.structure.json` files of `docs/__meta__/`, a corpus directory, a skills directory, a skill entry or a
skill's `SKILL.md`, whose permissions deny it, or a link on the way to it that cannot be followed. A structure
file the check expected, with no regular file standing in its place, is reported the same way, with nothing
refused to name.
It is reported once, at its path, and nothing under it is loaded. The message names the operation that was
refused, the path it was refused at, which may be one on the way, and the reason the operating system gave.

What the path held is then not checked, and every document it governs is listed as skipped in coverage, with no
rule run over it: a document that was not checked is never reported as clean. A structure file governs the
documents of its meta spec; a corpus directory, a skills directory and a skill entry hold the documents under
them. Every other corpus, skill and document is checked as if the path could be read.

`lorecraft check` reads the whole repository before it reports anything, and a refusal at that point stops the run
with an error naming the path and exit status 2, so it does not report this code today: it is reported only where
the workspace is read without that first read.

It has no level, so no configuration turns it off, and it is always reported as an error.

## Why is this bad?

Until the path can be reached, what it holds is not checked, so a violation there goes unreported and an agent
loads it unreviewed.

## Example

`docs/__meta__/guide.structure.json`, with its permissions removed:

```console
$ ls -l docs/__meta__/guide.structure.json
---------- 1 dev dev 24 Oct 12 10:02 docs/__meta__/guide.structure.json
```

## Use instead

Give the path back its permissions:

```console
$ chmod 644 docs/__meta__/guide.structure.json
$ ls -l docs/__meta__/guide.structure.json
-rw-r--r-- 1 dev dev 24 Oct 12 10:02 docs/__meta__/guide.structure.json
```

A directory needs its listing permission back instead, such as `chmod 755 docs/guide`. Where no regular file
stands, restore the structure file as a regular file inside the repository.
