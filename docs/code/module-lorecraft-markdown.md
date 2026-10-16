---
name: "module-lorecraft-markdown"
description: "The lorecraft.markdown package's responsibility, role, boundary and invariants: the one wrapper around Markdown parsing, which reads a document's text into frozen values and keeps wenmode's types from reaching any other package. Load when adding or moving code in lorecraft.markdown, reading or changing how Markdown text is parsed, how a heading's text or a link's URL is read or where the frontmatter block ends, or importing wenmode anywhere"
type: "pkg"
scope: "pkg:lorecraft.markdown"
---

# The `lorecraft.markdown` Package

## Responsibility

Wrap Markdown parsing, so that every Markdown operation Lorecraft performs goes through it. It changes when the
Markdown Lorecraft reads changes, or when the parser behind it does.

## Role

**Derivation.** It turns the text of a document into what that text says, a pure function of the text: no disk, no
cache across calls. It knows Markdown and nothing about what a document, an anchor or a check is, so the package
above it decides what a heading, a link or a frontmatter block means for a document.

## Belongs Here

- Code that parses Markdown text, or builds a value from what the parser reports.
- The tree a document reads into: its top-level blocks, its headings with the text each reads and renders as, and its links with their
  lines, as frozen values of this package's own.
- The scan that finds the raw frontmatter block, which mirrors the parser's frontmatter plugin.
- A fact about Markdown's grammar, such as which text is a heading, a code block or a link destination.
- `parse_markdown`, `parse_markdown_frontmatter` and the values they return, exposed by the package `__init__`.

## Belongs Elsewhere

| Code that… | Belongs in |
|---|---|
| Reads a file, or any bytes from the disk | `lorecraft.vfs` |
| Decodes the frontmatter block as YAML | `lorecraft.project`, over `lorecraft.yaml` |
| Derives an anchor, counts a section's words or numbers a repeated heading | `lorecraft.project` |
| Classifies a link as a path, a fragment or an external URL | `lorecraft.project` |
| Is generic over text and knows nothing of Markdown, such as where a line ends | `lorecraft.core` |

## Invariants

- wenmode is imported in this package alone, which a contract in `pyproject.toml` enforces; the one other import is
  the integration test that holds the frontmatter scan to the parser's plugin.
- Every other package reads a frozen value that this package declares, so an upgrade of the parser changes this
  package and no wenmode type escapes.
- It imports the standard library, wenmode and `lorecraft.core` only, which the layers contract enforces, so every
  package that reads Markdown can import it without a cycle.
- It is a pure function of its input. It performs no I/O and holds no state between calls.
- The shared parser instance keeps nothing of a document between parses and nothing changes its rules after they are
  built. This is checked again on every wenmode upgrade.
- The dialect is CommonMark with wenmode's frontmatter plugin and no GFM extension: a pipe table, strikethrough and a bare URL are not nodes.
- A link's URL is CommonMark-normalised: escapes and character references are decoded, then the value is
  percent-encoded.
- A heading is read once, in one walk, into one `MarkdownHeading` that carries both its texts and whether it is
  top-level: `text` keeps inline HTML and an image's alt text, and `rendered_text` drops both, as GitHub renders an
  anchor. The heading blocks of the tree are the same values as its `headings`.
- The frontmatter scan finds the block wenmode's plugin finds, which `tests/it/test_frontmatter_scan.py` pins.

## Examples

```python
# ❌ Bad — a module outside the wrapper imports the parser and walks its nodes: a mutable, pre-1.0 type now reaches
# the document model, and an upgrade edits every place that reads Markdown
from wenmode import Wenmode


def titles(text: str) -> list[str]:
    return [node.children[0].value for node in Wenmode().parse(text).children if node.type == 'heading']
```

```python
# ✅ Good — the module reads the frozen values `lorecraft.markdown` returns, and the parser stays behind it
from lorecraft.markdown import MarkdownHeading, parse_markdown


def titles(text: str) -> list[str]:
    return [block.text for block in parse_markdown(text).blocks if isinstance(block, MarkdownHeading)]
```

## Checklist

Before committing code, verify:

- [ ] No module outside `lorecraft.markdown` imports `wenmode`, except `tests/it/test_frontmatter_scan.py`
- [ ] Nothing in `lorecraft.markdown` reads the disk
- [ ] No wenmode type, mutable node or list is part of what the package returns
- [ ] `lorecraft.markdown` imports only the standard library, `wenmode` and `lorecraft.core`
- [ ] The parser is built with the frontmatter plugin only, and a wrapper test pins that a table, strikethrough and an
      autolink stay plain CommonMark
- [ ] A new wenmode version is checked against the shared parser's statelessness and the frontmatter scan test
- [ ] No identifier in `lorecraft.markdown` names a `lorecraft.project` concept (`Document`, `Anchor`,
      `FrontmatterNode`, a rule code)

## References

- [adr-001-snapshot-model](../arch/adr-001-snapshot-model.md) - Foundation: The Derivation role
- [adr-021-dependency-wrappers](../arch/adr-021-dependency-wrappers.md) - Foundation: Large dependencies stay behind owned wrapper layers
- [principle-single-responsibility](principle-single-responsibility.md) - Foundation: One reason to change
- [principle-information-hiding](principle-information-hiding.md) - Foundation: The parser's types stay behind the wrapper
