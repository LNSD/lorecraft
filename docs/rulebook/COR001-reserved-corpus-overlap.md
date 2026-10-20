---
name: "COR001-reserved-corpus-overlap"
description: "A directory under `docs/` has the name of a reserved corpus"
code: "COR001"
since: "0.4.0"
---

# reserved-corpus-overlap (COR001)

A directory under `docs/` has the name of a reserved corpus.

## What it does

Checks for a directory directly under `docs/` named like a reserved corpus, such as `docs/skills/` beside a
`skills` spec. The `skills` corpus has no directory: its documents are the skills of the agents' skills
directories, governed by the `skills` and `skills-<namespace>` specs of `docs/__meta__/`. The directory is
reported once, at its path, and ignored: none of the documents inside it is checked. The package states the rule;
no spec sets or changes it.

## Why is this bad?

The documents in the directory look governed, since a spec carries their corpus name, yet no rule is run
over them, so a violation there goes unreported.

## Example

`docs/skills/notes.md`, beside `docs/__meta__/skills.md`.

## Use instead

Move the documents to a corpus with another name, such as `docs/guides/`, and give that corpus a spec:

```console
$ mv docs/skills docs/guides
```
