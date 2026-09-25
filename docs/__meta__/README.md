# Meta Documentation

This directory holds the format specifications for `docs/`. Nothing here is registered anywhere: a file's own
name says what it governs, and a document's own path says which files govern it.

## What a Stem Matches

A **stem** is a filename here with its extensions dropped: `code`, `code-principle`. It is read as
`<corpus>` or `<corpus>-<namespace>`. The corpus names a directory under `docs/`; the namespace names a group
of documents inside it. A directory under `docs/` is a corpus only when a file at its stem exists here:

| Stem | Matches | Because |
|---|---|---|
| `<corpus>` | The directory `docs/<corpus>/` and every document directly in it; a subdirectory inside a corpus is ignored, not checked | A corpus is a flat directory that a stem here names |
| `<corpus>-<namespace>` | The documents `docs/<corpus>/<namespace>.md` and `docs/<corpus>/<namespace>-*.md` | A namespace matches a name that equals it or continues it with a hyphen; it may span several hyphenated words, so `code-python-errors` matches `python-errors.md` and `python-errors-*.md` but not `python-errorsx.md` |
| `<corpus>.<type>` | The documents in `docs/<corpus>/` whose frontmatter `type` is `<type>` | The type is a field the document itself declares |

So `code` matches all of `docs/code/`, and `code-principle` matches the subset named `principle.md` or
`principle-*.md`, `docs/code/principle-least-surprise.md` among them. A document is governed by its corpus
stem always, and by every narrower stem that matches, applied broad to narrow. Those stems **layer**: each is
a whole set of rules applied on its own, so a narrower stem states only what it adds, and it cannot escape
what a broader one already said. That is what a narrower stem is for: a rule that holds for a group but not
the corpus goes there, and stays out of the corpus file rather than becoming a condition inside it. Read
either direction from the shell:

```bash
ls docs/<corpus>/<namespace>.md docs/<corpus>/<namespace>-*.md   # from a stem here, the documents it matches
ls docs/__meta__/<corpus>*                                        # from a corpus, the stems that govern its documents
```

**A namespace is a group only once a stem here names it.** `docs/code/` holds documents under several
namespaces; those no `<corpus>-<namespace>` stem matches are governed by the corpus stem alone, which is the
normal case and not a gap to fill: `test-*` and `logging` answer to `code.*` and nothing else. Add a namespace
stem when a group's members genuinely share rules the rest of the corpus does not, and the group's documents
then answer to both. A namespace stem whose corpus has no stem of its own narrows nothing and is ignored.

The matching is by name and nothing else. A file added here starts governing the moment its name resolves, and
a group renamed under `docs/` stops matching the stem it used to, so rename the stem in the same change. A stem
whose namespace no longer matches any document still loads, and still must be valid JSON.

## A Specification and Its Checks

`<stem>.md` holds a specification in prose, and a reader is its audience. Beside it, each **aspect** of that
specification that a machine can decide is held again as data:

```
docs/__meta__/<stem>.<aspect>.json                          the rules for one aspect, in machine-checkable form
lorecraft check <aspect>                                   the check that applies them, once migrated
.agents/skills/docs-rules-check/scripts/check_<aspect>.py   the check that applies them, until then
```

Today `header` is the command and `structure` and `budget` are the scripts.

**The aspect name is the whole binding.** The stem says which documents a file governs, the aspect says which
check reads it, and a check needs no list of the files it applies to — it derives them from the document's own
path. Adding an aspect is adding those two files; nothing here has to be edited to know about it, which is why
this section names no aspect. To see the ones that exist:

```bash
ls docs/__meta__/*.json
lorecraft check --help
ls .agents/skills/docs-rules-check/scripts/
```

An aspect's file is written in whatever dialect its own check reads: the header aspect is JSON Schema,
documented in `lorecraft_core/schemas/header.py`; a script's dialect lives in its module docstring. A frontmatter
rule and a section-order rule are not the same shape of thing, and forcing them into one notation costs more
than it saves.

Four rules hold for every aspect, whatever it checks:

- **The prose is the authority; the JSON is the same rules in a form a script can apply.** They are one rule
  set in two forms — change both in the same commit. Nothing detects the drift when they disagree: the prose
  keeps saying one thing while the check enforces another, and whichever a reader consulted last wins.
- **A file at a corpus stem governs every document in that corpus.** `code.<aspect>.json` covers all of
  `docs/code/`.
- **A file at a namespace stem narrows the corpus file**, applying to the documents whose name the namespace
  matches. Several namespace stems can match one document; all apply, broadest first, so a namespace file
  states only what it adds, and a rule written once at the corpus stem cannot be escaped by a namespace file
  that forgets to restate it. A namespace file never governs alone: without `<corpus>.<aspect>.json` the
  aspect is unchecked for the whole corpus.
- **An absent file leaves that aspect unchecked**, and its documents are reported as unvalidated rather than
  as failures. A corpus is governed one aspect at a time. A file that is present but cannot be decoded is not
  a finding: the checker loads every specification in this directory before it reads a document, and one
  broken file stops the whole run. This README is not a specification; a listing of the workspace records it
  as skipped, which is expected.

## Discovering What Is Here

This file does not list the specifications. The naming convention above resolves any of them from a document's
own path, and an inventory here would be a second source of truth that goes stale on the first file that
lands. To see what is here, read the directory:

```bash
grep -m 3 -E '^(description|type|scope):' docs/__meta__/*.md
```

Use the `/docs-rules` skill to write a document under `docs/`, and `/docs-rules-check` to validate one. This
repository is the first corpus its own checks are pointed at: `just check-docs` runs every aspect over
`docs/`, and CI runs the same recipe.
