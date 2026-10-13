---
name: "adr-019-frontmatter-format"
description: "The frontmatter format: the closed list of YAML 1.2 constructs a frontmatter block may hold, what each reads as, and the refusal, as FM002 on its line, of every construct the list does not name, decided by lorecraft from the tokens and events it reads; a syntax error is FM002 in lorecraft's own words, classified from the parser's error; a key written twice at any depth is FM005. Load when changing what frontmatter accepts or refuses, or the diagnostics frontmatter.py reports for its syntax"
type: "adr"
status: "proposed"
---

# Frontmatter Format

## Context

[prd-018](prd-018-frontmatter-format.md) requires frontmatter to be a stated format, the same whichever parser reads
it: the constructs metadata is written with (FR-001 to FR-006), every other one reported on its line by name
(FR-007 to FR-013, FR-016), a key written twice reported at any depth (FR-014), and a block that cannot be read
reported in lorecraft's own words (FR-015).

lorecraft reads a block in `src/lorecraft/project/syntax/frontmatter.py`, building the value from a YAML parser's
token and event stream itself, and resolving plain scalars by YAML 1.2's core schema. Before this record, it refused
only anchors, aliases, tags and keys that are not strings; everything else was refused or accepted by the parser's
grammar. That grammar takes `%YAML` and `%TAG` directives of any 1.x version, explicit `? key` entries, the `...`
document-end marker, block-scalar indentation indicators and flow collections nested to any depth over many lines.
Keeping each of them meant code whose only purpose was to copy one parser's reading of a construct no frontmatter
needs, and a parser could not be changed without proving every one again.

The parser that reads the format is decided apart, in [adr-017](adr-017-yaml-parser.md).

## Specification

The block is the text between the opening `---` line and the closing `---` line. Terms are YAML 1.2's.

### Accepted

| Construct | Example | Reads as |
|---|---|---|
| The block as a whole: one block mapping | `name: a` on the first line | A mapping |
| A key: a plain, single-quoted or double-quoted scalar that reads as a string | `name:`, `"2026":`, `'a b':` | A string |
| A value of a block mapping: any accepted node, or nothing | `name: a`, `name:` | The node; nothing is null |
| A block mapping nested as a value, indented by spaces | `metadata:` then `  author: a` | A mapping |
| A block sequence, as a value, indented or not | `tags:` then `- a` or `  - a` | A list |
| An item of a block sequence: a scalar, a flow collection or a block mapping | `- a`, `- [a, b]`, `- name: a` then `  url: b` | The node |
| A flow sequence on one line, holding only scalars, possibly none | `tags: [a, "b c"]`, `tags: []` | A list |
| A flow mapping on one line, holding only `key: scalar` entries, possibly none | `size: {w: 1, h: 2}`, `size: {}` | A mapping |
| A plain scalar, on one line or continued on more indented lines | `title: A long` then `  title` | Resolved as below |
| A single-quoted scalar, `''` for a quote, on one or more lines | `t: 'it''s'` | A string |
| A double-quoted scalar, with YAML's escapes, on one or more lines | `t: "a\tbé"` | A string |
| A literal (`\|`) or folded (`>`) block scalar, with an optional `-` or `+` chomping indicator | `d: >-` then `  text` | A string |
| A comment, on its own line or after a node | `# note`, `name: a # note` | Nothing |
| Blank lines, CRLF line breaks, and a BOM before the first line | | Nothing |

A plain scalar resolves by YAML 1.2's core schema: `~`, `null`, `Null`, `NULL` and the empty scalar are null;
`true`/`True`/`TRUE` and `false`/`False`/`FALSE` are booleans; a decimal, `0o` octal or `0x` hexadecimal integer is
an integer; a decimal float is a float, unless it overflows to infinity. Anything else is a string: `yes`, `on`,
`2026-10-05`, `1:30`, `.inf` and `.nan` are strings.

### Refused

Each is `FM002` on its line, worded `found <what>, which frontmatter does not allow`.

| Construct | Example | FR |
|---|---|---|
| A directive | `%YAML 1.2`, `%TAG ! tag:x,2026:` | FR-007 |
| A document marker inside the block | `--- a`, `...` | FR-007 |
| An anchor, an alias or a merge key | `&a`, `*a`, `<<: *a` | FR-008 |
| A tag, of any form | `!!str 1`, `!x a`, `!<tag:x> a` | FR-009 |
| An explicit key | `? name` | FR-010 |
| An empty key | `: a` | FR-010 |
| A key that does not read as a string | `1: a`, `true: a`, `null: a`, `[a]: b` | FR-010 |
| A flow collection spread over lines | `tags: [a,` then `  b]` | FR-011 |
| A flow collection holding a collection | `a: [[1], {b: 2}]`, `a: [b: c]` | FR-011 |
| A block-scalar indentation indicator | `d: \|2` | FR-012 |
| A flow collection as the block itself | `{name: a}`, `[a, b]` | FR-011 |
| A block sequence as an item of a block sequence | `- - a`, `-` then `  - a` | FR-016 |

Everything the Accepted table does not list is refused the same way. A block that is in block style but not a
mapping at the top, such as a block sequence, a single scalar or an empty block, stays
`FM003 non-mapping-frontmatter`, as today.

### Syntax errors

A block written only with accepted constructs can still be broken: a bad indent, an unclosed quote, a tab. Each is
`FM002`, worded by lorecraft, never by the parser. lorecraft classifies the parser's error into one of the kinds
below, from what the error carries: its class, the problem and the context it names, the two marks, and the block's
own text at them. The line reported is the one the writer fixes, which for an unclosed construct is where it opened.

| Kind | Example | Reported on | Label | Help |
|---|---|---|---|---|
| `: ` inside a plain value | `a: b: c` | The value's line | `` this value holds `: ` `` | Quote the value: `a: "b: c"` |
| A key indented under a text value | `name: a` then `  description: b` | The indented line | `` `description` is indented under `name`, whose value is text `` | Align it with the key it belongs beside |
| A line that lines up with no key or item | `metadata:` then `    a: 1` then `  b: 2` | The line | `this line's indentation matches no key or item above it` | Indent it like the keys or items it belongs with |
| A line that is neither `key: value` nor `- item` | `just words` between two keys | The line | `` this line is not `key: value` or `- item` `` | Add `: ` after the key, or quote a value that runs on |
| An unclosed quote | `name: "abc` | The line the quote opens on | `this quote is never closed` | Close it on the line it continues to, or remove it |
| Text after a closing quote | `name: "a" b` | The line | `text follows the closing quote` | Put the whole value inside the quotes |
| A tab used for indentation | `⇥b: c` | The line | `a tab indents this line` | Indent with spaces |
| An escape double quotes do not know | `a: "\q"`, `a: "\xZZ"` | The line | `` `\q` is not an escape `` | Write `\\` for a backslash, or use single quotes |
| A character that cannot start a plain value | `` a: `b` ``, `a: @b` | The line | `` a plain value cannot start with `@` `` | Quote the value |
| A control character | `b` followed by U+0007 | The line | `the block holds the control character U+0007` | Remove it |

An unclosed flow collection is spread over lines, so it is the refusal of FR-011, not a syntax error. An error no
kind matches is reported on the parser's problem line as `the block cannot be read from this line on`, with no
parser text; every syntax-error probe is held to a kind, so the fallback stays a safety net.

## Decision

1. **A frontmatter block holds only the constructs the Specification accepts**, and the docstring of
   `frontmatter.py` states that list (FR-001 to FR-004, FR-006).
2. **Plain scalars resolve by YAML 1.2's core schema, as before**, as the Specification states (FR-005).
3. **Every construct the Specification refuses, and every one it does not list, is `FM002 invalid-yaml` on the line
   it is written on**, worded `found <what>, which frontmatter does not allow`, where `<what>` names the construct
   (FR-007 to FR-013, FR-016). The first such construct in the block is the one reported.
4. **lorecraft refuses each construct from the tokens and events it reads**, never by relying on a parser's grammar
   to reject it, so the format holds whichever parser produces the stream.
5. **A key written twice in one mapping is `FM005 duplicate-key`, at any depth** (FR-014), block or flow, reported
   on the later key's line and pointing back at the first. The block still decodes, the later value standing, so
   its other fields are still read and checked.
6. **A syntax error inside the subset is `FM002`, worded by lorecraft, never by the parser** (FR-015). Each error
   is classified into a kind of the Specification's Syntax errors table, from the error's class, texts and marks,
   and reported with that kind's label and help, on the line the writer fixes. No parser text reaches a diagnostic.

## Alternatives Considered

- **Accept what PyYAML's grammar accepted.** No document changes its outcome. Not chosen: it keeps a version setter,
  directive scanning, scanner overrides and a wording table, each present only to copy PyYAML on constructs no
  frontmatter needs, and ties the format to one parser.
- **Refuse flow mappings too.** Flow mappings are rare in frontmatter. Not chosen: the owner accepted them on one
  line, like flow sequences, which Jekyll and Hugo tags use.
- **Keep the last value of a nested duplicate key.** It is what the parser did. Not chosen: YAML leaves which value
  wins undefined, so one of the two lines says nothing the document means.
- **Accept a flow mapping as the block itself**, such as `{name: a}`. It is a mapping like any other. Not chosen:
  the owner requires the top level in block style, one key per line, so a block always reads the same way.
- **Accept a block sequence as an item of a block sequence**, such as `- - a`. It is plain YAML. Not chosen: it is
  rare in frontmatter and easy to misread, and `- [a, b]` already writes a list of lists on one line.
- **Refuse a block mapping as an item of a block sequence**, so items are scalars or one-line collections. Not
  chosen: a list of objects, such as an `authors:` list of `name` and `url` entries, is common frontmatter and would
  be pushed onto one long line.
- **Show the parser's own message.** No classification to maintain, and within the format its words match today's
  on every probe but one typo. Not chosen: the owner does not expose a parser's messages; they name parser
  internals (`<block end>`, `simple key`), say nothing of the fix, and change with the parser.
- **Keep today's wording, rewritten into PyYAML's.** No message changes. Not chosen: it keeps a rewrite table and
  tests against PyYAML, the parser-copying code this format removes, and still names parser internals.
- **Report a nested duplicate as `FM002`, keeping `FM005` for the top level.** No nested key positions to track.
  Not chosen: one mistake would carry two codes, and a duplicate inside a nested mapping would make the whole block
  unreadable, hiding `name`, `description` and every schema check.
- **Report every duplicate as `FM002`**, refused by the format like any other construct. Not chosen: it retires
  `FM005`, a published code; every duplicate would hide the whole block; and its level could no longer be set apart
  from a syntax error's.

## Consequences

- **Some blocks that read before are now `FM002`**: those using a construct the Specification refuses. None is in
  lorecraft's own repository. Each is reported on its line, with what to remove named.
- **A nested duplicate key is now reported**, where its last value used to win silently.
- **Every `FM002` syntax-error message changes**, to lorecraft's label and a help line. For an unclosed quote the
  line moves to where the quote opens, and for a line that is not `key: value` to that line, both where the writer
  fixes it.
- **lorecraft owns the classification**: it reads the parser's error texts to pick a kind, so a parser upgrade that
  rewords an error can move it to the fallback. The pinned parser and a test per kind catch that before release.
- **The parser code in `frontmatter.py` shrinks**: the directive and version handling, the scanner overrides and the
  wording table go. The event walking, the core-schema resolution and the refusals stay, joined by the new ones.
- **Each row of the Specification has a test of its own**: an accepted row decodes to what the table says, and a
  refused row is `FM002` on its line next to a near miss the format accepts (NFR-002).
- **What stays true**: the four outcomes of decoding a block, and the value every block inside the subset decodes
  to (NFR-001).

## Checklist

- [ ] The docstring of `frontmatter.py` states the Specification's accepted constructs
- [ ] Each accepted row of the Specification has a test that decodes it to what the table says
- [ ] Plain scalars resolve by YAML 1.2's core schema, with `.inf` and `.nan` read as strings
- [ ] Each refused row of the Specification is `FM002` on its line, worded `found <what>, which frontmatter does not
  allow`, with a test that triggers it and a near miss that does not
- [ ] Each refusal is decided from the token or event stream, not from a parser error
- [ ] A key written twice in a mapping at any depth is `FM005` on the later key's line, pointing back at the first
- [ ] Each kind of the Syntax errors table has a test: its example is `FM002` with that kind's label and help, on
  the line the table names
- [ ] No diagnostic quotes a parser's message text
- [ ] No syntax-error probe falls back to `the block cannot be read from this line on`
- [ ] Every frontmatter block in lorecraft's own repository decodes to the same value as before

## References

- [prd-018](prd-018-frontmatter-format.md) - Source: The frontmatter format this decision answers
- [module-lorecraft-project](../code/module-lorecraft-project.md) - Related: The package whose frontmatter decoding
  this decision governs
