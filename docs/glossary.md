# Glossary

A glossary of documentation framework terminology used throughout Lorewright.

## Documents and collections

### Corpus

A collection of documents of one kind under `docs/`, such as `docs/code/` or `docs/feat/`. A corpus has a format specification that governs its documents.

### Code rules

The collection of conventions that applies across the codebase, documented in `docs/code/`.

### Code rule document

A Markdown document in `docs/code/` stating a code convention. It is authoritative for that convention and uses [frontmatter](#frontmatter) for discovery.

### Feature document

A document in `docs/feat/` describing existing toolkit behavior, such as a capability or component. It is authoritative for the behavior it describes.

### Agent skill

A reusable set of agent instructions, sometimes with supporting scripts. Skills live in `.agents/skills/`.

## Metadata and specifications

### Frontmatter

YAML metadata at the start of a Markdown document, between `---` delimiters. Fields such as `name`, `description`, `type`, and `status` help classify and discover documents.

### Format specification

A document in `docs/__meta__/` that defines the metadata, structure, and content rules for a corpus or document group.

### Prefix specification

An additional specification selected by a document's filename prefix, such as `code-python.md` for `python-*` code rule documents. It adds or narrows corpus requirements.

### Type specification

A feature document structure specification selected by the frontmatter `type`. It defines required sections for that document type.

### Components

A feature document's frontmatter list of related modules, skills, or specifications, each identified by a type prefix.

### Status

A feature document's maturity label: `development`, `unstable`, `experimental`, or `stable`.

## Validation

### Machine-checkable companion

A JSON file beside a format specification that represents one aspect of its rules for a checker: frontmatter (`.header.json`), section structure (`.structure.json`), or prose length (`.budget.json`).

### Check

A script that validates one aspect of documentation against a machine-checkable companion. Document checks cover frontmatter, structure, and prose budget.

### Prose budget

The maximum prose length allowed for a document or one of its sections, as defined by a budget specification.
