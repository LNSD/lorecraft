---
name: "spec"
description: "The specification files under docs/__meta__/: the file types the *.md and *.structure.json patterns claim and the stem left before the pattern, how a stem makes a directory under docs/ a corpus, how corpus and namespace stems layer onto a document, and what an absent or malformed file means. Load when adding a corpus or a namespace specification, or asking why a document is governed, ungoverned or not checked at all"
type: "meta"
status: "experimental"
components: "module:lorecraft.project"
---

# Specification Files

## Summary

A repository declares the rules for its documents as specification files in `docs/__meta__/`. Nothing
registers them: a file's name says which documents it governs and which check reads it, and a document's own
path says which files govern it. Every command that reads a repository loads these files the same way.

## Table of Contents

1. [Key Concepts](#key-concepts)
2. [Architecture](#architecture)
3. [Limitations](#limitations)
4. [Base and Extension](#base-and-extension)
5. [References](#references)

## Key Concepts

- **Corpus**: A directory under `docs/` whose documents specifications govern, as
  [workspace](workspace.md) lays out.
- **File type**: What a specification file is, claimed by a file name pattern: `*.md` claims the prose and
  `*.structure.json` the structure specification. A file's extension is only what follows its last dot.
- **Stem**: A specification filename with its pattern's suffix stripped: `<corpus>` or `<corpus>-<namespace>`.
- **Structure specification**: `<stem>.structure.json`, the part of a specification a check can decide: the
  section rules, the word caps, the token budget and the frontmatter schema, each read by its own check.
- **Prose**: `<stem>.md`, the specification written for a reader. It is the authority; the JSON beside it is
  the same rules in a form a check applies.
- **Base**: The document an extension adds to: `cli-check.md` is the base of `cli-check-frontmatter.md`, and the
  corpus specification `feat.md` is the base of `feat-cli.md`.
- **Extension**: A document that adds to its base, which its name alone identifies.

## Architecture

### Filenames

A file in `docs/__meta__/` is a specification file when a file type's pattern claims its name: `<stem>.md` or
`<stem>.structure.json`. The stem opens with a corpus name, lowercase letters, digits and underscores starting
with a letter or an underscore, and a corpus name holds no hyphen, so the corpus ends at the first hyphen: a
corpus of several words is spelled with underscores, so `docs/cli_specs/` is governed by `cli_specs.md` and
narrowed by `cli_specs-<namespace>.md`. What follows is the namespace: lowercase letters and digits in
hyphen-separated words, starting with a letter. A stem holds no dot. A file whose name does not parse, such as
`README.md`, `1abc.md`, `feat-2col.md` or a `<stem>.<token>.json` that no pattern claims, is left out,
and so is a namespace stem whose corpus has no file at its own stem, or no directory under `docs/`. A
`<stem>.header.json` from before the frontmatter schema moved into the structure specification is claimed by no
pattern, like any other unknown JSON file, so it is left out and not read.

### Loading

Every structure specification whose stem the rules above keep is read and validated before any document, from
one snapshot of the tree. A prose file is never read: its name alone counts. Nor is any file at a stem left out
above, such as a namespace stem whose corpus has no directory. A structure specification that cannot be read,
is not valid JSON, or does not state usable rules in its dialect stops the whole command with an error naming
the file.

### Governed or Not

Each check decides on its own whether a document is governed. A namespace specification never stands in for its
corpus specification: with no corpus structure file, a document is ungoverned for every check. With one, the
structure check governs it whatever keys the files state, the budget check when a structure file that applies
sets `tokens`, and the frontmatter check only when the corpus file itself states `frontmatter`. An ungoverned
document is listed, never failed.

## Limitations

- The structure specification is the only machine-checkable file type; a second needs a new pattern, a new
  check and a new dialect in the package.
- A rule stated in prose that no structure specification holds is not checked: the prose and the JSON can drift,
  and nothing detects it.

## Base and Extension

Within a corpus, **a name's base is the longest existing name it continues with a hyphen**, and the name
extends it: `cli-check-frontmatter.md` extends `cli-check.md`, which extends `cli.md`.

A specification's stem is not read that way from its first character. Its corpus is the name of a directory
under `docs/`, not a shorter name the stem continues, so the corpus is set aside first. The **corpus
specification**, the stem that is the corpus alone, is the base of every specification in the corpus because
it governs every document in the directory. The rest of the stem, the namespace, is a document name, and
follows the rule above: `feat-cli` governs `cli` and would be extended by a `feat-cli-check` governing
`cli-check`, as `cli.md` is by `cli-check.md`.

| Base | Extensions | Because |
|------|------------|---------|
| `feat` | `feat-cli` | `feat` is the corpus `docs/feat/` |
| `feat-cli` | `feat-cli-check`, were it added | Namespace `cli-check` continues `cli` |
| `cli-check.md` | `cli-check-frontmatter.md`, `cli-check-structure.md` | The names continue `cli-check` |

A document is governed by its corpus specification, then by each namespace specification whose namespace equals
its filename or is a hyphen-delimited prefix of it, broad to narrow: `feat-cli` governs `cli.md` and
`cli-check.md`, not `client.md`. Each is applied on its own, so an extension only adds rules and cannot relax
its base.

### References Point to the Base

An extension names its base; a base never names its extensions, neither in its references nor inline.
`feat-cli.md` links to `feat.md` and `cli-check-frontmatter.md` to `cli-check.md`; neither base links back. For a
specification this covers its JSON files too: a base's `description` names no extension, and `feat.md` does
not point at any `feat-cli.*.json`. A base is written without knowing what extends it, so adding, renaming or
removing an extension never edits the base, and the base carries no list of extensions to go stale.

## References

- [workspace](workspace.md) - Related: the layout of the corpora and documents these files govern
- [cli](cli.md) - Related: the command line that reads these files
