---
name: "spec"
description: "The spec files under docs/__meta__/: the file types claimed by *.md and *.spec.json, how names select corpora and layers, and what absent or malformed files mean. Load when adding a corpus or namespace spec, or asking why a document is governed, ungoverned or not checked at all"
type: "meta"
status: "experimental"
components: "module:lorecraft.project"
---

# Spec Files

## Summary

A repository declares the rules for its documents as spec files in `docs/__meta__/`. Nothing
registers them: a file's name says which documents it governs and which rules read it, and a document's own
path says which files govern it. Every command that reads a repository loads these files the same way.

## Table of Contents

1. [Key Concepts](#key-concepts)
2. [Architecture](#architecture)
3. [Limitations](#limitations)
4. [Base and Extension](#base-and-extension)
5. [References](#references)

## Key Concepts

- **Corpus**: A directory under `docs/` whose documents specs govern, as
  [workspace](workspace.md) lays out.
- **File type**: What a spec file is, claimed by a file name pattern: `*.md` claims the prose and
  `*.spec.json` the structure file. A file's extension is only what follows its last dot.
- **Spec name**: A spec filename with its pattern's suffix stripped: `<corpus>` or
  `<corpus>-<namespace>`.
- **Structure file**: `<name>.spec.json`, the part of a spec a check can decide: the
  section rules, the word caps, the token budget and the frontmatter schema, each read by its own rules.
- **Prose**: `<name>.md`, the spec written for a reader. It is the authority; the JSON beside it is
  the same rules in a form a check applies.
- **Base**: The document an extension adds to: `spec-structure.md` is the base of `spec-structure-outline.md`, and the
  corpus spec `feat.md` is the base of `feat-cli.md`.
- **Extension**: A document that adds to its base, which its name alone identifies.

## Architecture

### Filenames

A file in `docs/__meta__/` is a spec file when a file type's pattern claims its name: `<name>.md` or
`<name>.spec.json`. The spec name opens with a corpus name:
lowercase letters, digits and underscores starting with a letter or an underscore. A corpus name holds no
hyphen, so the corpus ends at the first hyphen: a corpus of several words is spelled with underscores, so `docs/cli_specs/` is governed by
`cli_specs.md` and narrowed by `cli_specs-<namespace>.md`. What follows is the namespace: lowercase letters and
digits in hyphen-separated words, starting with a letter. A spec name holds no dot. A file whose name
does not parse, such as `README.md`, `1abc.md`, `feat-2col.md` or a `<name>.<token>.json` that no pattern claims,
is left out, and so is a namespace spec whose corpus has no file at its own name, or no directory under
`docs/`. A numeric placeholder spec such as `adr-0000` alone establishes its corpus, given `docs/adr/`. The reserved corpora `meta` and `skills` load without a directory (`LC101` reports one);
the `meta` specs govern the spec files. A `<name>.header.json` is claimed by no pattern, so it is left out and not read.

### Loading

At a spec name, `<name>.spec.json` is the structure file. Other readable files no file type claims are ignored without a diagnostic.

Every selected structure file is read and validated before any document, from one snapshot. Only selected files
are read as specs. Invalid JSON or unusable rules are load failures. `check` reports
these (`LC001` undecodable, `LC003` malformed, `LC004` unusable) and unreadable structure files (`LC002`) as errors at the file, skips governed documents, checks the rest
and exits `1`. `inspect` exits `2` on a load failure. `check` reports unreadable files under `docs/` as `LC002`;
unlistable `docs/` or `docs/__meta__/`, and unreported refusals outside `docs/`, exit `2`.

### Governed or Not

Each part of a document a rule reads is governed on its own. A namespace spec never stands in for its
corpus spec: with no corpus structure file, a document is ungoverned for every part, except a skill's frontmatter and 500-line budget, which the
builtin Agent Skills layer governs. With one, its structure is
governed whatever keys the files state, its outline or its budget when a structure file that applies states an
outline or sets `tokens` or `lines`, and its frontmatter only when the corpus file itself states `frontmatter`. No rule over an
ungoverned part runs: the part is reported as [coverage](cli-check.md#output), never failed.

## Limitations

- Structure JSON is the only machine-checkable dialect; a second dialect needs a new pattern and rules
  in the package.
- A rule stated in prose that no structure file holds is not checked: the prose and the JSON can drift,
  and nothing detects it.

## Base and Extension

Within a corpus, **a name's base is the longest existing name it continues with a hyphen**, and the name
extends it: `spec-structure-outline.md` extends `spec-structure.md`, which extends `spec.md`.

A spec name is not read that way from its first character. Its corpus is the name of a directory
under `docs/`, not a shorter name the spec name continues, so the corpus is set aside first. The
**corpus spec**, whose name is the corpus alone, is the base of every spec in the corpus
because it governs every document in the directory. The rest of the name, the namespace, is a document name, and
follows the rule above: `feat-cli` governs `cli` and would be extended by a `feat-cli-check` governing
`cli-check`, as `cli.md` is by `cli-check.md`.

| Base | Extensions | Because |
|------|------------|---------|
| `feat` | `feat-cli` | `feat` is the corpus `docs/feat/` |
| `feat-cli` | `feat-cli-check`, were it added | Namespace `cli-check` continues `cli` |
| `spec-structure.md` | `spec-structure-outline.md`, `spec-structure-budget.md` | The names continue `spec-structure` |

A document is governed by its corpus spec, then by each namespace spec whose namespace equals
its filename or is a hyphen-delimited prefix of it, broad to narrow: `feat-cli` governs `cli.md` and
`cli-check.md`, not `client.md`. Each is applied on its own: an extension adds or tightens rules and cannot
relax its base. The order fixes only the order of the report; a document passes only when it passes every
spec, and each diagnostic names the spec it breaks.

### References Point to the Base

An extension names its base; a base names none of its extensions, in references or inline. Across corpora, the
document that builds on another links to it, and the other does not link back. `LC505`, `LC506` and `LC507`
check these directions. For a spec, the rule also covers its JSON files. A base is written without knowing
what extends it, so adding, renaming or removing an extension never edits the base or leaves a list to go stale.

## References

- [workspace](workspace.md) - Related: the layout of the corpora and documents these files govern
- [cli](cli.md) - Related: the command line that reads these files
