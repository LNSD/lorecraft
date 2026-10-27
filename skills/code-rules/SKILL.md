---
name: code-rules
description: Load the repository's code rules that apply to the work at hand, from docs/code/, reading their frontmatter first and only the ones whose triggers match. Use before planning or writing code, or when asked about the repository's conventions, standards, or design principles. Not for checking finished code; see /code-rules-check
compatibility: Reads files only. Requires the code rules to be kept as Markdown documents in docs/code/ with name and description frontmatter
allowed-tools: Bash(grep *) Bash(ls docs/*)
---

# Code Rules

A repository that uses Lorecraft keeps its code rules (also called code rules), the conventions for how its code
is written, as a corpus in `docs/code/`, one convention or topic per code rule. This skill loads only their frontmatter, and you
choose what to read from it. Selecting well is the whole job: read what the task needs, nothing more.

If `docs/code/` does not exist, say so: the repository has no code rules to load. Its corpus spec, if one
exists, is `docs/__meta__/code.md`; `/docs-rules-creator` sets one up.

## 1. The catalog

Run this first; it is the whole index:

```bash
grep -m 3 -E '^(description|type|scope):' docs/code/*.md
```

Where the repository also keeps architecture decision records in `docs/arch/`, an **accepted** one binds code as
a code rule does: it states how the code is built. List them too, and treat only those whose `status` is
`accepted` as binding:

```bash
grep -m 4 -E '^(description|status):' docs/arch/adr-*.md
```

Each `description` says what its document covers and, where the corpus spec asks for one, a trigger
clause — `Load when …` or similar — naming the situations the document governs. Other fields, such as `type`
or `scope`, are whatever `docs/__meta__/code.md` defines; read its frontmatter section once if their meaning is
not obvious.

## 2. Selecting

Match the task against the trigger clauses, then:

- **Take the most specific match, then load its base chain.** For every hyphen-prefix ancestor of the matched
  filename, read the corresponding existing `.md` document in `docs/code/`, broadest first. For example, a
  match to [`python-typing-cast`](https://github.com/LNSD/lorecraft/blob/main/docs/code/python-typing-cast.md)
  loads the existing [`python-typing`](https://github.com/LNSD/lorecraft/blob/main/docs/code/python-typing.md)
  ancestor; the `python` ancestor is absent in this corpus. Skip a missing intermediate name and continue with
  any more specific existing ancestor. The matched document and its base chain count as one selection.
- **Expect two to four selections.** One is common. A selection includes its matched document and its base
  chain. More than four means the task is unscoped, or you are matching topics instead of triggers.
- **Break ties by specificity**: a document scoped to the package or directory being changed over a global
  one, where the frontmatter says which is which.
- **Read nothing adjacent.** If no trigger matches, say so: a gap in the code rules is worth reporting.

Read selections at `docs/code/<name>.md`, or `docs/arch/<name>.md` for a decision record. Do not re-read what is
already in context.

## 3. Code rules that apply to all design work

Some code rules — design principles, usually a `principle-*` group — govern every change, so no task will match
their triggers. Treat their catalog `description`s as the principles themselves and design against every one. Read
a full principle document only to argue one: to justify a decision, settle a disagreement, or cite it in a
review. Asked for the principles, read them all and summarise.

## 4. Applying

The code rules are the repository's decisions, and they outrank general practice and your defaults. Where one
seems wrong for the task, follow it and raise the conflict; do not silently deviate. Each code rule usually
ends with a checklist: hold it while writing, since `/code-rules-check` checks the result against it.
