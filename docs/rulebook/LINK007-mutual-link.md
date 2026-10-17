---
name: "LINK007-mutual-link"
description: "Two documents of different corpora link to each other"
code: "LINK007"
since: "0.4.0"
---

# mutual-link (LINK007)

Two documents of different corpora link to each other.

## What it does

Checks for a link from a document to a document of another corpus, `docs/<corpus>/<name>.md`, that links back to
it. Both documents are reported, each on its own link, so either side sees the finding. A link to a document of
the same corpus, to a file that is no document, to a missing file or to the document itself is not reported. No
meta spec key states the rule: every document of a corpus that states a structure file is held to it.

## Why is this bad?

Across corpora, one document builds on the other: a decision record on the requirement it answers, a feature
document on the code rule it follows. The one that is built on stands without the other. A link in both
directions makes each depend on the other, so neither can be read, changed or removed alone.

## Example

`docs/arch/prd-001.md` and `docs/arch/../feat/guide.md`, each linking the other:

```markdown
# Guide

Read [the requirement](../arch/prd-001.md).
```

```markdown
# Requirement

The feature is described in [the guide](../feat/guide.md).
```

## Use instead

Keep the link in the document that builds on the other, and drop it from the one built on:

```markdown
# Requirement

The feature is described by the guide that builds on it.
```
