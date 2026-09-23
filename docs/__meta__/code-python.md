---
name: "code-python"
description: "Structure template for `docs/code/python-*.md` rule documents. Load when creating or editing Python convention docs in docs/code/"
type: "meta"
scope: "global"
---

# Python Convention Rule Document Template

**MANDATORY structure for ALL `docs/code/python-*.md` documents**

The `python-*` group documents how Python source is written in this project: what a construct is named, where
it is declared, how it is spelled, and what a reader is entitled to assume when they meet it. One document
owns one construct.

## Structure

Every python rule document contains the following parts in order.

### Frontmatter (required)

| Field | Value | Notes |
|-------|-------|-------|
| `name` | `python-<aspect>` or `python-<aspect>-<facet>` | Matches filename minus `.md` |
| `description` | Discovery-optimized summary | No trailing period |
| `type` | `"core"` | Always |
| `scope` | `"global"` | Always |

Every value is **quoted**, `type` included. This is the form [code.md §2](code.md#2-frontmatter-requirements)
writes and the form the sibling templates pin; a bare `type: core` is a defect to fix, not a variant.

A `python-*` document is `"core"`. A rule about packaging, distribution shape, or build configuration governs
where code lives rather than how it is written, which is a different subject and takes `"arch"`
([code.md §2](code.md#2-frontmatter-requirements)).

See [code.md §2](code.md#2-frontmatter-requirements) for field rules and description guidelines.
See [code.md §3](code.md#3-naming-schema) for full naming rules.

### Header

#### Title (required)

H1 naming the construct the document governs, as a noun phrase: "Type Annotations", "Module Layout",
"Exception Handling", "Name Choice". A stdlib API the document is wholly about may appear in the title, in
backticks: "Structured Records (`dataclasses`)", "Context Managers (`contextlib`)".

The title is not the filename respelled. `python-errors-handling` is "Error Handling", not "Python Errors
Handling".

#### Scope line (omitted)

**No scope line.** A `python-*` document is `scope: "global"` and governs all Python code in the project, so a
bold line saying so restates the frontmatter, the title, and the corpus-wide mandate in
[code.md §1](code.md#1-core-principles). The H1 is followed directly by the doctrine paragraph.

Write one only where the document's subject is genuinely narrower than Python source — a single file type, a
single kind of declaration — so the line says something `scope: "global"` cannot.
See [code.md §5](code.md#5-document-structure).

#### Doctrine (required)

One or two short paragraphs between the H1 and section 1. They do two jobs, and a document may need either or
both:

- **State the governing idea.** The one sentence that, if a reader remembered nothing else, would let them
  derive most of the numbered sections. Bold it when the whole document hangs off it.
- **Place the document among its neighbours.** One-line ownership pointers naming what this document does not
  own, in the phrasing fixed below.

No heading, and no list of the document's own sections: the headings already are that list, and a second copy
of them goes stale on the first edit.

### Body

#### Numbered Rule Sections (required)

Every content section is `## N. Title`, numbered from 1, in reading order.

- **Two or more sections.** A document with one section is a section of another document.
- **The title states the rule, not the topic.** "Never Catch Bare `Exception`", "Annotate Every Public
  Signature", "Every Finding Names Its Document". Title Case. A reader scanning only the headings has read the
  document.
- **Sections are flat.** No `###` inside a numbered section: one that wants sub-headings is two sections.
- **Each section opens with the rule**, in one or two sentences, then the reason it exists, then its examples.
  The reason is what survives; a rule with no stated cost is one the next reader talks themselves out of.
- **`## References`, `## Checklist`, and `## External References` are not numbered.**
- **No Table of Contents.** Cross-section links use the generated anchor: `([§3](#3-naming-and-visibility))`.

#### Examples

Labelled and governed in full by [code.md §6](code.md#6-content-guidelines). What the group adds:

- The fence language is the language of the artifact the rule governs: `python` by default, `toml` for
  `pyproject.toml`, `console` for a command line, `markdown` for a document the checker reads, unlabelled for
  a file tree.
- **Invented subjects, real package names.** Classes, functions, attributes, and the failure stories in the
  marker comments are fabricated. Packages, subpackages, and console scripts keep the names they actually
  have, in this project and in the dependency graph alike, because the name is the lesson rather than evidence
  for it. No file path appears inside an example, and no prose points at a real module as proof of the rule.
- Bad before Good.
- **Good-only is correct** where there is no instructive mistake, only a shape the reader has not met. Prefer
  it to inventing a strawman.
- A Bad/Good pair may share one fence or occupy two. Pick one and hold it within a document.
- The clause after the marker names the cost concretely.

A section that is purely about placement, naming, or a prohibition may carry no example at all. State the rule
and the reason and stop rather than padding with code that shows nothing.

#### Voice

The corpus-wide mandate is carried by [code.md §1](code.md#1-core-principles), so sections do not restate it.
Write each rule as a declarative sentence ("`strict=True` is mandatory on every `zip`", "Nothing from `typing`
is imported where a builtin generic will do") rather than as bolded `**MANDATORY**`, `**ALWAYS**`, or
`**DO NOT**` before every paragraph. Shouting on every rule ranks none of them; bold marks the one clause a
skimming reader must not miss, which means a few per document at most.

Prose is hard-wrapped at 110 columns. Tables, code fences, and link lines may run past it.

#### Ownership Pointers

[code.md §1](code.md#1-core-principles) gives every rule exactly one home, and siblings link rather than
restate. The group writes that link in a fixed phrasing so it stays greppable, and so an author reaching for a
sentence finds the pointer instead of writing a second copy of the rule:

| Form | Use |
|------|-----|
| `{{Subject}} is owned by [{{doc}}]({{doc}}.md).` | Something adjacent that this document does not govern |
| `This document owns {{subject}}.` | Claiming the boundary from this side |
| `This document is about {{subject}}.` | Closing a doctrine paragraph that has just handed work away |
| `- [{{doc}}]({{doc}}.md) - Related: Owns {{subject}}` | The same pointer, in `## References` |

A pointer names the rule and never repeats it, and never repeats its example. Where a document restates a
sibling's rule "so the reader does not have to click", delete the restatement and link.

### Footer

#### References (required)

A python document links its neighbours. Entries are `- [{{name}}]({{name}}.md) - {{Relationship}}: {{what the
reader gets there}}`, with continuation lines indented two spaces.

- A document that specializes a parent (`python-<aspect>-<facet>`) names the parent `Extends`, **first** in
  the list. The parent names its children `Related`, never `Extends`: specialization points one way, and a
  pair that each call the other `Extends` has recorded no relationship at all.
- Siblings inside the group are `Related`. A `principle-*` document is `Foundation`.
- The description says what the reader gets by following the link, not what the target is called.
  "Related: Owns the comment a `# type: ignore` must carry" earns its line; "Related: Comments" does not.

See [code.md §4](code.md#4-cross-reference-rules) for relationship types and direction rules.

#### Checklist (required)

Opens with the fixed lead-in `Before committing code, verify:`, then one `- [ ]` item per rule, in the order
the sections state them. Each item is a check a reviewer can run against a diff without re-reading the
document, so it names the artifact to look for rather than the principle behind it. Continuation lines indent
six spaces, aligning under the item's text.

#### External References (optional)

Links to external articles, specifications, or upstream documentation that explain the subject in depth. Not
project-internal, and not a dependency's release notes, migration map, or install instructions, which are
status ([code.md §1](code.md#1-core-principles)).

#### Order of Checklist and References

**Checklist, then References, then External References**, as
[code.md §5](code.md#5-document-structure) states and [code.md §7](code.md#7-template) emits. The Checklist is
the last thing a reader does in the document; the two reference sections are navigation away from it and stay
adjacent.

### Sub-Group Members

A `python-<aspect>` document may be specialized by `python-<aspect>-<facet>` documents. When it is:

- **The parent carries rule content.** It states the invariants the facets make operational, and it is never a
  router: a document whose only job is to list its children is prohibited
  ([code.md §1](code.md#1-core-principles)).
- **The child labels the parent `Extends`**, first in `## References`, and its doctrine paragraph names what
  the parent owns.
- **A facet exists because the parent had two reasons to change**, not because the parent got long. Splitting
  on length produces two documents that must be read together, which is worse than one that is read once.

A sub-group with no parent document is legal: the facets sit side by side as `Related` siblings and the shared
prefix is what groups them. Do not add a parent purely so that one exists.

## Template

Every python rule document MUST follow this template:

````markdown
---
name: "python-<aspect>[-<facet>]"
description: "{{Brief summary. Load when [trigger conditions], no period}}"
type: "core"
scope: "global"
---

# {{Construct the document governs}}

{{Doctrine: the governing idea, and what a neighbour owns. See Structure > Doctrine.}}

## 1. {{The rule, stated as a title}}

{{The rule in one or two sentences, then why it exists. See Structure > Numbered Rule Sections.}}

```python
# ❌ Bad — {{what went wrong, and what it cost when it shipped}}
{{incorrect_example()}}
```

```python
# ✅ Good — {{why this is right, and what it prevents}}
{{correct_example()}}
```

## 2. {{The next rule}}

{{Rule, reason, examples.}}

## Checklist

Before committing code, verify:

- [ ] {{Check a reviewer can run against a diff, for section 1}}
- [ ] {{Check for section 2}}

## References

- [{{parent}}]({{parent}}.md) - Extends: {{What the parent owns}}
- [{{sibling}}]({{sibling}}.md) - Related: {{What the reader gets there}}
- [{{principle-name}}]({{principle-name}}.md) - Foundation: {{The principle behind this document}}

## External References {{OPTIONAL}}

- [{{External reference title}}]({{url}})
````

## References

- [code](code.md) - Extends: Base code rules documentation format specification
