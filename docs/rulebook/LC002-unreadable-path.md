---
name: "LC002-unreadable-path"
description: "A path cannot be read"
code: "LC002"
since: "0.3.0"
---

# unreadable-path (LC002)

A path cannot be read.

## What it does

Checks for paths the operating system refuses to let the check read, list or look up: a structure file, one of
the `<name>.spec.json` files of `docs/__meta__/`, or the legacy `<name>.structure.json`, that it cannot read; a
corpus directory, a skills directory or a skill entry that it cannot list; and a link on the way to a skill, a
skill entry or a skill's `SKILL.md` that it cannot follow. A structure file the check expected, with no regular
file standing in its place, is reported the same way, with nothing refused to name.
It is reported once, at its path, and nothing under it is loaded. The message names the operation that was
refused, the path it was refused at, which may be one on the way, and the reason the operating system gave.

What the path held is then not checked. A structure file it cannot read governs documents, and each of them is
listed as skipped in coverage, with no rule run over it: a document that was not checked is never reported as
clean. A corpus directory, a skills directory or a skill entry it cannot list holds documents the check never
learns of, so none is listed, and this diagnostic is the only sign of them. Every other corpus, skill and
document is checked as if the path could be read.

Four refusals are not reported under this code, and each stops the run with an error naming the path and exit
status 2: a `docs/` or `docs/__meta__/` that cannot be listed, since with it nothing can be checked; a
document, or any other file the check reads, that cannot be read, including a regular `SKILL.md`; a symlink
whose target cannot be read; and a directory that nothing loads, such as one under `docs/` that no meta spec
names or one inside a skill, that cannot be listed.

It has no level, so no configuration turns it off, and it is always reported as an error.

## Why is this bad?

Until the path can be reached, what it holds is not checked, so a violation there goes unreported and an agent
loads it unreviewed.

## Example

`docs/__meta__/guide.spec.json`, with its permissions removed:

```console
$ ls -l docs/__meta__/guide.spec.json
---------- 1 dev dev 24 Oct 12 10:02 docs/__meta__/guide.spec.json
```

## Use instead

Give the path back its permissions:

```console
$ chmod 644 docs/__meta__/guide.spec.json
$ ls -l docs/__meta__/guide.spec.json
-rw-r--r-- 1 dev dev 24 Oct 12 10:02 docs/__meta__/guide.spec.json
```

A directory needs its listing permission back instead, such as `chmod 755 docs/guide`. Where no regular file
stands, restore the structure file as a regular file inside the repository.
