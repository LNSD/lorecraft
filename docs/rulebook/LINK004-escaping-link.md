---
name: "LINK004-escaping-link"
description: "A relative link climbs above the bound of its link base"
code: "LINK004"
since: "0.3.0"
---

# escaping-link (LINK004)

A relative link climbs above the bound of its link base.

## What it does

Checks relative links and images in documents, meta specs and skills. Documents and meta specs read links from
their own directory and may climb within the repository, but not above its root. Skills and resources read links
from the skill root and may not climb above that root.

A path that climbs and comes back down inside its bound stays inside. A URL with a scheme, an absolute link, or
a fragment-only link spells no relative path, so none is reported.

## Why is this bad?

A link above its base's bound names a path the project cannot reliably provide. Skills may be installed
independently; documents and meta specs cannot name paths outside the repository snapshot.

## Example

`docs/guide/setup.md`:

```markdown
# Checklist

Start from [the repository file](../../../outside.md).
```

## Use instead

Keep the link within its base's bound:

```markdown
# Checklist

Start from [the repository file](../code/guide.md).
```
