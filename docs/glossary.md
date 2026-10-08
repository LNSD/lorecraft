# Glossary

A glossary of documentation framework terminology used throughout Lorecraft.

Lorecraft governs two kinds of document: a [meta spec](#meta-spec) states the rules, and a [spec](#spec) follows them. One word names one thing: where an older name is still in use, an entry gives it as an alias or a former name. **Code rule** and **feat doc** are the principal names everywhere. **Code spec** and **feat spec** are their generic synonyms.

## Specs and collections

### Corpus

A collection of specs of one kind under `docs/`, such as `docs/code/` or `docs/feat/`. A corpus is governed by its [corpus meta spec](#corpus-meta-spec), and the kind of spec it holds is named after it.

### Spec

A document in a [corpus](#corpus), governed by the [meta specs](#meta-spec) its path selects. It is authoritative for what it states and uses [frontmatter](#frontmatter) for discovery. Each corpus holds one kind: a [code rule](#code-rule), a [feat doc](#feat-doc) or an [arch spec](#arch-spec).

### Code rule

A document in `docs/code/` stating a code convention. **Code spec** is its generic synonym. A project keeps its code rules in `docs/code/`, and the `/code-rules` skill loads them. A code rule is a document, not a [rule](#rule).

### Feat doc

A document in `docs/feat/` describing a toolkit feature from its user's point of view, such as a capability or a component. Because it is authoritative for the behavior it describes, it is also the reference that end-to-end test coverage can be measured against. **Feat spec** is its generic synonym. A project documents its features as feat docs in `docs/feat/`.

### Code spec

The generic synonym for a [code rule](#code-rule), a document in `docs/code/` stating a code convention. It is used where the generic spec category matters.

### Feat spec

The generic synonym for a [feat doc](#feat-doc), a document in `docs/feat/` describing a toolkit feature. It is used where the generic spec category matters.

### Arch spec

A spec in `docs/arch/`: a PRD, stating what a capability must do and why, or an ADR, stating how something is built and why. PRD and ADR stay the everyday names of its two namespaces. An accepted arch spec binds code as a code rule does.

### Base and extension

Within a corpus, a name's **base** is the longest existing name it continues with a hyphen, and the name **extends** it: `spec-structure-outline` extends `spec-structure`, which extends `spec`. A name's bases, followed to the shortest, form its **chain**. The terms hold for specs and for meta specs alike, where the [corpus meta spec](#corpus-meta-spec) is the base of every [namespace meta spec](#namespace-meta-spec) in its corpus. An extension adds or tightens, and never relaxes its base.

### Agent skill

A reusable set of agent instructions, sometimes with supporting scripts.

### Resource

A Markdown file inside an [agent skill](#agent-skill) other than its top-level `SKILL.md`, at any depth, such as a reference the skill loads on demand. It is named where an agent reaches it, through any symlink inside the skill, and located at the [resolved](#resolved-path) file that path leads to.

## Metadata and meta specs

### Frontmatter

YAML metadata at the start of a Markdown document, between `---` delimiters. Fields such as `name`, `description`, `type`, and `status` help classify and discover documents.

### Meta spec

A spec that governs other specs: a document in `docs/__meta__/` stating the metadata, structure and content rules for a corpus or a namespace in it, together with the [machine-checkable](#machine-checkable-companion) files beside it at the same [meta spec name](#meta-spec-name). Formerly *format specification*, or just *specification*.

### Corpus meta spec

The meta spec whose name is a corpus alone, such as `code`. It governs every spec in its corpus, and is the base of every namespace meta spec there. Formerly *corpus specification*.

### Namespace meta spec

A meta spec selected by a spec's filename, when a namespace equals the name or is a hyphen-delimited prefix of it: `code-python.md` for `python-*` code rules, `feat-cli.md` for `cli-*` feat docs. It extends its base, the corpus meta spec or a shorter namespace meta spec it continues, and cannot relax it. Formerly *namespace specification*.

### Meta spec name

What a meta spec file's name says it governs: the filename with its [file type](#file-type)'s pattern suffix stripped, so `code.md` and `code.structure.json` are both at the name `code`. It is `<corpus>`, the name of a corpus meta spec, or `<corpus>-<namespace>`, the name of a [namespace meta spec](#namespace-meta-spec), such as `code-python`. Formerly *specification name*.

### Aspect

The part of a name after its corpus: in `docs/code/python-fn.md`, or the [meta spec name](#meta-spec-name) `code-python-fn`, the corpus is `code` and the aspect is `python-fn`. An aspect splits into a namespace and a [facet](#facet): `python-fn` is the namespace `python` plus the facet `fn`. The middle of a meta spec filename, `structure` in `code.structure.json`, is not an aspect: what that file is comes from its [file type](#file-type).

### Facet

What a spec's name adds to a namespace that matches it: name = namespace + facet. The name `python-typing` is the namespace `python` plus the facet `typing`. A facet is relative to the namespace chosen: `python-typing-unreachable` has the facet `typing-unreachable` under `python`, and would have `unreachable` under a `python-typing` namespace. It is empty when the namespace is the whole name.

### Components

A feat doc's frontmatter list of related modules, skills, or meta specs, each identified by a type prefix.

### Status

A feat doc's maturity label: `development`, `unstable`, `experimental`, or `stable`.

## Validation

### Machine-checkable companion

A JSON file of a meta spec, beside its prose, that holds the rules a checker can decide: the structure file, `<name>.structure.json`, holding the section structure with its word caps, the token budget and the frontmatter schema. Formerly *structure specification*.

### File type

What a file in `docs/__meta__/` is, claimed by a file name pattern: `*.md` claims a meta spec's prose and `*.structure.json` its structure file. A file's extension is only what follows its last dot, so `code.structure.json` is a JSON file the structure file type claims; a file no pattern claims is not part of a meta spec.

### Rule

One judgment `lorecraft check` makes of a subject, a spec, a skill, a resource of a skill or a symlink of the skill layout, identified by a code in a group named by its prefix, such as `FM001`, and a kebab-case name, such as `missing-frontmatter`. A rule over a spec reads the keys of a machine-checkable companion, and runs only when the spec is governed for what it reads. "Rule" names a check and nothing else: a [code rule](#code-rule) is a document, not a check.

### Diagnostic

One occurrence of a rule, located at the root-relative path of the subject it was found in: a line when it has one, a severity, the code, a message, and the labels, help and notes around it. Diagnostics are what `lorecraft check` prints, counts, and serialises, in path order, so each one stands on its own once diagnostics from many subjects are listed together.

### Word cap

The maximum prose words one section of a document may hold, its subsections included, as set by a `words` key on an outline entry of a structure file and checked by `lorecraft check` as `LEN003`. It keeps the section concise; code and tables are not counted.

### Token budget

The maximum tokens a whole document file may hold, frontmatter, code and tables included, as set by the `tokens` key of a structure file and checked by `lorecraft check` as `LEN001`. It keeps the document cheap to load; tokens are OpenAI's `o200k_base`, counted the same whichever agent reads the document.

## Toolkit internals

### Snapshot

What one scan of a repository saw: every listing, every regular file's bytes and every symlink's target under `docs/`, down to a fixed depth, and under the skills directories, at any depth. A snapshot is never patched: the next one is a new value, from a full scan or from the previous snapshot with only the paths filesystem events name scanned again, and it equals what a full scan would see. Two snapshots are equal exactly when nothing they cover changed. The virtual view answers the filesystem boundary's operations from one snapshot without touching the disk.

### Change set

The difference of two snapshots, one entry per path: added, modified or deleted. An entry whose kind changed, such as a directory turned into a symlink, counts as deleted. It is computed from the two states, never from the filesystem events between them, so a save that leaves the bytes unchanged is no change.

### Symlink

A link in the filesystem, pointing at another path. The snapshot records each symlink's target, and only the filesystem boundary follows one. The project model records where a document's or skill's symlinks lead, apart from its identity, so a symlink retargeted to another file changes what the identity reads without changing any bytes. Never called just a "link".

### Resolved path

A path relative to the workspace root with every [symlink](#symlink) on the way followed, so no symlink is on the way to it or at it: with `.agents/skills/review` a link to `../../skills/review`, the resolved path of `.agents/skills/review/SKILL.md` is `skills/review/SKILL.md`. The project model names a document or skill where an agent reaches it and locates it at the resolved path that name leads to. Whether a path is resolved depends on the snapshot it is found in, so the code tells one apart by its type alone.

### Markdown link

A link written in a document, `[text](destination)`, held as a node of the document's parse tree with its destination as written. Turning the destination into a path is pure, and whether that path names a document is a question for the project model. Never called just a "link".

### Revision

One set of inputs, the snapshot and the declarations, and the database built from them: the state every check behind one report reads. An event of any kind changes an input, and the next state of the workspace is a new revision, new inputs and a new database, which may keep the query results the change between the two left valid.

### Project model

What a repository declares, as Lorecraft reads it: its corpora, meta specs, specs and skills, and where each one's symlinks lead. It is derived from the declarations and the structure of the snapshot, never from what a document says. The code calls it the workspace model.
