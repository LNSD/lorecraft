---
name: "LINK006-missing-base-link"
description: "A document that extends another does not link to it under References"
code: "LINK006"
since: "0.4.0"
---

# missing-base-link (LINK006)

A document that extends another does not link to it under References.

## What it does

Checks for a document whose base is not linked in its `References` section. A document's base is the narrowest
document of its corpus whose name the document's name continues after a hyphen: `python-fn` for
`python-fn-unchecked`, even when `python-fn-unchecked` sits two names below it. A document with no such name
has no base and is not judged. The link must lead to the base's file, and lie between the `References` heading
and the next heading of its level or above, so a link in the text or under `External References` does not count.
A meta specification of `docs/__meta__/` is judged the same way, its base looked for among the specifications.
No meta spec key states the rule: every document of a corpus that states a structure file, and every meta
specification, is held to it.

The finding is reported on the `References` heading, or on the title when the document has no such section.

## Why is this bad?

An extension specialises its base and is read with it. A reader, or an agent, that loads the extension and finds
no link to the base has no way to reach what the extension builds on.

## Example

`docs/guide/setup-extra.md`, beside `docs/guide/setup.md`:

```markdown
# Setup extra

## References

- [other](other.md) - Related: Something else
```

## Use instead

Name the base, first under References:

```markdown
# Setup extra

## References

- [setup](setup.md) - Extends: What this document specialises
- [other](other.md) - Related: Something else
```
