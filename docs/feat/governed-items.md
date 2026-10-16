---
name: "governed-items"
description: "The shared model description for corpus documents and listed skill entries; Load when using model-resolved item identity, locations, link bases or origin facts"
type: "component"
status: "experimental"
components: "module:lorecraft.project"
---

# Governed Markdown Items

## Summary

The workspace model describes a corpus document or listed skill entry through one common item reference and descriptor. The reference gives the stable logical path used to identify and report the item; the descriptor also records where the current snapshot reads its text and the origin facts consumers need. This lets callers handle both item kinds through a shared model contract while preserving their different link bases and governance.

## Table of Contents

1. [Key Concepts](#key-concepts)
2. [Architecture](#architecture)
3. [Usage](#usage)
4. [Limitations](#limitations)
5. [References](#references)
6. [Code References](#code-references)

## Key Concepts

- **Item reference**: The root-relative logical path where the model lists an item and where findings identify it.
- **Read location**: The path in the current snapshot from which an item's Markdown is read; a linked skill entry can differ from its item reference.
- **Origin facts**: The expected name and provenance supplied for the item's kind, used by consumers to retain name checks and attribution.
- **Active facets**: The kinds of checks the model enables for an item.

## Architecture

`WorkspaceModel.describe_item` accepts an existing corpus-document or skill-entry reference and returns the same descriptor shape for either. Corpus documents use their document directory as the relative-link base; listed skill entries use the listed skill directory. A linked skill's logical path remains tied to its listed entry when the resolved Markdown read location changes. When multiple agents reach one listed skill, the model retains one skill identity. Skill resource files continue to be listed lazily by the existing resource APIs; this descriptor does not migrate resource consumers.

## Usage

### Describe an item

```python
item = model.describe_item(ref)

report_path = item.ref.path
markdown_path = item.read_location
link_base = item.link_base
```

`ref` is an existing document or skill reference. The descriptor also exposes `origin`, `governance_corpus`, `aspect_name`, and `active_facets`; consumers can use these facts without inferring governance identity from frontmatter content.

| Item kind | Relative-link base | Expected name and provenance |
|-----------|--------------------|------------------------------|
| Corpus document | The document's containing directory | Filename stem and governing frontmatter schema path, when present |
| Listed skill entry | The listed skill directory | Listed directory name and resolved directory target when linked |

## Limitations

- The shared descriptor covers corpus documents and listed skill entries; resource consumers still use the existing resource discovery behavior.
- Skill entries activate frontmatter and Markdown facets. Corpus-document facets reflect the governance available in the workspace model.
- Layout symlinks remain separate non-text subjects.

## References

- [workspace](workspace.md) - Base: the repository layout and snapshot that supply corpus documents and skills
- [PRD-020](../arch/prd-020-skills-corpus.md) - Source: requirements for governed-item identity and descriptors
- [ADR-023](../arch/adr-023-governed-items.md) - Source: the governed-item reference and origin classification decision

## Code References

- `src/lorecraft/project/item.py` - Defines the common item reference, descriptor, origin facts and facets
- `src/lorecraft/project/workspace/model.py` - Resolves item descriptors from document and skill references
