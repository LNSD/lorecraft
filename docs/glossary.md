# Glossary

A glossary of documentation framework terminology used throughout Lorecraft.

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

### Violation

One rule a document breaks, as a check reports it: a line, a rule identifier, and a message. It does not name the document, since a check sees only the part of the document it reads, such as the headings or the frontmatter. Violations are collected per document, in that document's report.

### Finding

A [violation](#violation) located in its document: the violation plus the document's root-relative path. Findings are what `lorecraft check` prints, counts, and serialises, so each one stands on its own once findings from many documents are listed together.

### Prose budget

The maximum prose length allowed for a document or one of its sections, as defined by a budget specification.

## Toolkit internals

### Snapshot

What one scan of a repository saw: every listing, every regular file's bytes and every symlink's target under `docs/` and the skills directories, down to a fixed depth. A snapshot is replaced whole by the next scan, never patched, and two snapshots are equal exactly when nothing they cover changed. The virtual view answers the filesystem boundary's operations from one snapshot without touching the disk.

### Change set

The difference of two snapshots, one entry per path: added, modified or deleted. An entry whose kind changed, such as a directory turned into a symlink, counts as deleted. It is computed from the two states, never from the filesystem events between them, so a save that leaves the bytes unchanged is no change.
