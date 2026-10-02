# Meta Documentation

This directory holds the format specifications for `docs/`. Nothing here is registered anywhere: a file's own
name says what it governs, and a document's own path says which files govern it.

## What a Specification Name Matches

A **specification name** is a filename here with its pattern's suffix stripped: `code`, `code-principle`. It is
read as `<corpus>` or `<corpus>-<namespace>`. The corpus names a directory under `docs/`; the namespace names a
group of documents inside it. A directory under `docs/` is a corpus only when a file at its name exists here:

| Specification name | Matches | Because |
|---|---|---|
| `<corpus>` | The directory `docs/<corpus>/` and every document directly in it; a subdirectory inside a corpus is ignored, not checked | A corpus is a flat directory that a specification name here names |
| `<corpus>-<namespace>` | The documents `docs/<corpus>/<namespace>.md` and `docs/<corpus>/<namespace>-*.md` | A namespace matches a name that equals it or continues it with a hyphen; it may span several hyphenated words, so `code-python-errors` matches `python-errors.md` and `python-errors-*.md` but not `python-errorsx.md` |

So `code` matches all of `docs/code/`, and `code-principle` matches the subset named `principle.md` or
`principle-*.md`, `docs/code/principle-least-surprise.md` among them. A document is governed by its corpus
specification always, and by every narrower specification whose name matches, applied broad to narrow. Those
specifications **layer**: each is a whole set of rules applied on its own, so a narrower one states only what it
adds, and it cannot escape what a broader one already said. That is what a narrower one is for: a rule that holds
for a group but not the corpus goes there, and stays out of the corpus file rather than becoming a condition
inside it. Read either direction from the shell:

```bash
ls docs/<corpus>/<namespace>.md docs/<corpus>/<namespace>-*.md   # from a name here, the documents it matches
ls docs/__meta__/<corpus>*                                        # from a corpus, the specifications governing it
```

**A namespace is a group only once a specification name here names it.** `docs/code/` holds documents under
several namespaces; those no `<corpus>-<namespace>` name matches are governed by the corpus specification alone,
which is the normal case and not a gap to fill: `test-*` and `logging` answer to `code.*` and nothing else. Add a
namespace specification when a group's members genuinely share rules the rest of the corpus does not, and the
group's documents then answer to both. A namespace specification whose corpus has no specification of its own
narrows nothing and is ignored.

The matching is by name and nothing else. A file added here starts governing the moment its name resolves, and
a group renamed under `docs/` stops matching the specification name it used to, so rename the specification in
the same change. A specification whose namespace no longer matches any document still loads, and still must be
valid JSON.

## A Specification and Its Checks

`<name>.md` holds a specification in prose, and a reader is its audience. Beside it, the rules of that
specification that a machine can decide are held again as data, in a file at the same specification name:

```
docs/__meta__/<name>.md               the specification, in prose
docs/__meta__/<name>.structure.json   the structure specification: the rules a check can decide
lorecraft check <check>               a check that reads its own keys from the structure specifications
```

What a file here is comes from its **file type**, which a file name **pattern** claims: `*.md` claims the prose,
and `*.structure.json` the structure specification. A file's extension is only what follows its last dot, so
`code.structure.json` is a JSON file that the structure file type claims. The structure specification is the one
machine-checkable file type: it carries the section rules, the word caps, the token budget and the frontmatter
schema. `lorecraft check structure` enforces the caps with the section outline,
`lorecraft check budget` the global `tokens` key, since it reads the raw file rather than its parse, and
`lorecraft check frontmatter` the global `frontmatter` key, as `check budget` reads `tokens`.

**The filename is the whole binding.** The specification name says which documents a file governs, the pattern
that claims it says which checks read it, each its own keys, and a check needs no list of the files it applies
to — it derives them from the document's own path. Adding a check is adding the keys it reads, or a file type
with its pattern and its dialect; nothing here has to be edited to know about it. To see the files and the
checks that exist:

```bash
ls docs/__meta__/*.json
lorecraft check --help
```

A machine-checkable file is written in whatever dialect its checks read: the structure dialect is documented in
`lorecraft/project/schemas/structure.py`. A dialect that is not JSON Schema may also have its shape published
as one under `docs/schemas/`, generated by `just gen`, which a file names in its `$schema` key so an editor can
validate it as it is written. The `frontmatter` value in `<name>.structure.json` is a Draft 2020-12 JSON Schema
whose root must state `"type": "object"`, with no `$id` anywhere in it; a frontmatter rule and a section-order
rule are not the same shape of thing, and forcing them into one notation costs more than it saves.

Four rules hold for every machine-checkable file, whatever it checks:

- **The prose is the authority; the JSON is the same rules in a form a check can apply.** They are one rule
  set in two forms — change both in the same commit. Nothing detects the drift when they disagree: the prose
  keeps saying one thing while the check enforces another, and whichever a reader consulted last wins.
- **A file at a corpus specification name governs every document in that corpus.** `code.structure.json`
  covers all of `docs/code/`.
- **A file at a namespace specification name narrows the corpus file**, applying to the documents whose name
  the namespace matches. Several namespace specifications can match one document; all apply, broadest first, so
  a namespace file states only what it adds, and a rule written once at the corpus specification name cannot be
  escaped by a namespace file that forgets to restate it. A namespace file never governs alone: without
  `<corpus>.structure.json` its rules are unchecked for the whole corpus.
- **An absent file leaves its rules unchecked**, and its documents are reported as unvalidated rather than
  as failures. A corpus is governed one check at a time. The same holds for the `frontmatter` key: without it
  in `<corpus>.structure.json`, frontmatter is unchecked for the whole corpus, whatever a namespace file says.
  A file that is present but cannot be decoded is not a finding: the checker loads every specification in
  this directory before it reads a document, and one broken file stops the whole run. This README is not a
  specification, so the workspace model leaves it out.

## Discovering What Is Here

This file does not list the specifications. The naming convention above resolves any of them from a document's
own path, and an inventory here would be a second source of truth that goes stale on the first file that
lands. To see what is here, read the directory:

```bash
grep -m 3 -E '^(description|type|scope):' docs/__meta__/*.md
```

Use the `/docs-rules` skill to write a document under `docs/`, and `/docs-rules-check` to validate one. This
repository is the first corpus its own checks are pointed at: `just check-docs` runs every check over
`docs/`, and CI runs the same recipe.
