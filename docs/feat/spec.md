---
name: "spec"
description: "The meta spec files under docs/__meta__/: the file types the *.md and *.structure.json patterns claim and the meta spec name left before the pattern, how a meta spec name makes a directory under docs/ a corpus, how corpus and namespace meta specs layer onto a document, and what an absent or malformed file means. Load when adding a corpus or a namespace meta spec, or asking why a document is governed, ungoverned or not checked at all"
type: "meta"
status: "experimental"
components: "module:lorecraft.project"
---

# Specification Files

## Summary

A repository declares the rules for its documents as meta spec files in `docs/__meta__/`. Nothing
registers them: a file's name says which documents it governs and which rules read it, and a document's own
path says which files govern it. Every command that reads a repository loads these files the same way.

## Table of Contents

1. [Key Concepts](#key-concepts)
2. [Architecture](#architecture)
3. [Limitations](#limitations)
4. [Base and Extension](#base-and-extension)
5. [References](#references)

## Key Concepts

- **Corpus**: A directory under `docs/` whose documents meta specs govern, as
  [workspace](workspace.md) lays out.
- **File type**: What a meta spec file is, claimed by a file name pattern: `*.md` claims the prose and
  `*.structure.json` the structure file. A file's extension is only what follows its last dot.
- **Meta spec name**: A meta spec filename with its pattern's suffix stripped: `<corpus>` or
  `<corpus>-<namespace>`.
- **Structure file**: `<name>.structure.json`, the part of a meta spec a check can decide: the
  section rules, the word caps, the token budget and the frontmatter schema, each read by its own rules.
- **Prose**: `<name>.md`, the meta spec written for a reader. It is the authority; the JSON beside it is
  the same rules in a form a check applies.
- **Base**: The document an extension adds to: `spec-structure.md` is the base of `spec-structure-outline.md`, and the
  corpus meta spec `feat.md` is the base of `feat-cli.md`.
- **Extension**: A document that adds to its base, which its name alone identifies.

## Architecture

### Filenames

A file in `docs/__meta__/` is a meta spec file when a file type's pattern claims its name: `<name>.md` or
`<name>.structure.json`. The meta spec name opens with a corpus name, lowercase letters, digits and
underscores starting with a letter or an underscore, and a corpus name holds no hyphen, so the corpus ends at the
first hyphen: a corpus of several words is spelled with underscores, so `docs/cli_specs/` is governed by
`cli_specs.md` and narrowed by `cli_specs-<namespace>.md`. What follows is the namespace: lowercase letters and
digits in hyphen-separated words, starting with a letter. A meta spec name holds no dot. A file whose name
does not parse, such as `README.md`, `1abc.md`, `feat-2col.md` or a `<name>.<token>.json` that no pattern claims,
is left out, and so is a namespace meta spec whose corpus has no file at its own name, or no directory under
`docs/`. A `<name>.header.json` from before the frontmatter schema moved into the structure file is
claimed by no pattern, like any other unknown JSON file, so it is left out and not read.

### Loading

Every structure file whose name the rules above keep is read and validated before any document, from
one snapshot of the tree. A prose file is never read: its name alone counts. Nor is any file at a meta spec
name left out above, such as a namespace meta spec whose corpus has no directory. A structure file that cannot be read,
is not valid JSON, or does not state usable rules in its dialect stops the whole command with an error naming
the file.

### Governed or Not

Each part of a document a rule reads is governed on its own. A namespace meta spec never stands in for its
corpus meta spec: with no corpus structure file, a document is ungoverned for every part. With one, its structure is
governed whatever keys the files state, its outline or its budget when a structure file that applies states an
outline or sets `tokens`, and its frontmatter only when the corpus file itself states `frontmatter`. No rule over an
ungoverned part runs: the part is reported as [coverage](cli-check.md#output), never failed.

## Limitations

- The structure file is the only machine-checkable file type; a second needs a new pattern, new
  rules and a new dialect in the package.
- A rule stated in prose that no structure file holds is not checked: the prose and the JSON can drift,
  and nothing detects it.

## Base and Extension

Within a corpus, **a name's base is the longest existing name it continues with a hyphen**, and the name
extends it: `spec-structure-outline.md` extends `spec-structure.md`, which extends `spec.md`.

A meta spec name is not read that way from its first character. Its corpus is the name of a directory
under `docs/`, not a shorter name the meta spec name continues, so the corpus is set aside first. The
**corpus meta spec**, whose name is the corpus alone, is the base of every meta spec in the corpus
because it governs every document in the directory. The rest of the name, the namespace, is a document name, and
follows the rule above: `feat-cli` governs `cli` and would be extended by a `feat-cli-check` governing
`cli-check`, as `cli.md` is by `cli-check.md`.

| Base | Extensions | Because |
|------|------------|---------|
| `feat` | `feat-cli` | `feat` is the corpus `docs/feat/` |
| `feat-cli` | `feat-cli-check`, were it added | Namespace `cli-check` continues `cli` |
| `spec-structure.md` | `spec-structure-outline.md`, `spec-structure-budget.md` | The names continue `spec-structure` |

A document is governed by its corpus meta spec, then by each namespace meta spec whose namespace equals
its filename or is a hyphen-delimited prefix of it, broad to narrow: `feat-cli` governs `cli.md` and
`cli-check.md`, not `client.md`. Each is applied on its own: an extension adds or tightens rules and cannot
relax its base. The order fixes only the order of the report; a document passes only when it passes every
meta spec, and each diagnostic names the meta spec it breaks.

### References Point to the Base

An extension names its base; a base never names its extensions, neither in its references nor inline.
`feat-cli.md` links to `feat.md` and `spec-structure-outline.md` to `spec-structure.md`; neither base links back. For a
meta spec this covers its JSON files too: a base's `description` names no extension, and `feat.md` does
not point at any `feat-cli.*.json`. A base is written without knowing what extends it, so adding, renaming or
removing an extension never edits the base, and the base carries no list of extensions to go stale.

## References

- [workspace](workspace.md) - Related: the layout of the corpora and documents these files govern
- [cli](cli.md) - Related: the command line that reads these files
