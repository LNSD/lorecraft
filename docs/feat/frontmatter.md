---
name: "frontmatter"
description: "The frontmatter format, accepted values, refused YAML constructs and diagnostic wording. Load when writing frontmatter or investigating LC202 and LC205 findings"
type: "feature"
status: "experimental"
components: "module:lorecraft.project,module:lorecraft.rules"
---

# Frontmatter Format

## Summary

A document's opening `---` block holds a block mapping of metadata. Lorecraft reads a small, stated part of
YAML 1.2 into JSON values. `LC202` names a construct the format refuses or explains a syntax error; `LC205`
reports a key written twice in the same mapping, including a nested one.

## Table of Contents

1. [Key Concepts](#key-concepts)
2. [Usage](#usage)
3. [Limitations](#limitations)
4. [Refused Constructs](#refused-constructs)
5. [Syntax Errors](#syntax-errors)
6. [Repeated Keys](#repeated-keys)
7. [References](#references)
8. [Code References](#code-references)

## Key Concepts

- **Block mapping**: The top level of the frontmatter, with one `key: value` entry per line.
- **Flow collection**: A list in `[]` or a mapping in `{}`. Here it stays on one line and holds only scalars.
- **Plain scalar**: An unquoted value, read by YAML 1.2's core schema when its whole text matches a core value.
- **Refusal**: An `LC202 invalid-yaml` finding on the line of a construct outside this format. Its label begins
  `found` and ends `which frontmatter does not allow`.

## Usage

A block begins and ends with `---`. Its top level is a block mapping with string keys, plain or quoted:

```yaml
---
name: guide
description: "A short guide: start here"
tags: [docs, guide]
metadata:
  author: Ada
  reviewed: true
authors:
- name: Ada
  url: https://example.org/ada
---
```

| Place | Accepted form | Value read |
|---|---|---|
| Key | Plain, single-quoted or double-quoted scalar that reads as text | String |
| Mapping value | Accepted node, or nothing after `:` | Node, or null |
| Nested mapping | Block mapping indented with spaces | Mapping |
| Block sequence | Value of a mapping, indented or unindented | List |
| Sequence item | Scalar, one-line flow collection or block mapping | Item's value |
| Flow sequence | One line, only scalars; `[]` is allowed | List |
| Flow mapping | One line, only string keys and scalar values; `{}` is allowed | Mapping |
| Plain scalar | One line or continued on more-indented lines | YAML 1.2 core value or string |
| Quoted scalar | Single quotes (`''` for a quote) or double quotes (YAML escapes); may span lines | String |
| Block scalar | Literal `|` or folded `>`, optionally with `-` or `+` chomping | String |
| Comment, blank line, CRLF or initial BOM | Outside values | No value |

Inside single- or double-quoted values, U+0085, U+2028 and U+2029 stay as text, with surrounding spaces kept.
They start no new line, so `---` or `...` after one stays in the value.

Plain `~`, `null` (in any of its three case forms) and an empty scalar read as null. `true` and `false` in
lower, title or upper case read as booleans. Decimal, `0o` octal and `0x` hexadecimal integers read as numbers;
decimal floats also read as numbers unless they overflow to infinity. Other plain text stays text, including
`yes`, `on`, dates such as `2026-10-05`, times such as `1:30`, `.inf` and `.nan`. Quote a value when its exact
text must be kept.

## Limitations

- A block sequence, scalar or empty block at the top level is `LC203 non-mapping-frontmatter`.
- A flow collection at the top level is `LC202`, even when it contains a mapping.
- The format excludes YAML constructs used to share nodes or choose custom types; write the value directly.
- Applicable frontmatter schemas are checked from broader to narrower governance layers. A missing-field
  diagnostic is reported only once when multiple schemas require the same field. Frontmatter rules, including
  the `name` comparison, run only when at least one applicable schema is loaded; a valid value can still fail a
  schema that applies to the item.
- `---` delimiters ending in a lone `\r` are not recognized as a frontmatter block.

## Refused Constructs

Each of these is `LC202` on its [document line](cli-check.md#key-concepts). The label is
`found <what>, which frontmatter does not allow`;
`<what>` is as shown below. The first refused construct in the block is reported.

| Written construct | Example | `<what>` |
|---|---|---|
| Directive at the start of a line | `%YAML 1.2` | `the directive %YAML` |
| Document marker inside the block | `--- a`, `...` | `the document marker ---` or `the document marker ...` |
| Anchor | `&base` | `the anchor &base` |
| Alias | `*base` | `the alias *base` |
| Plain merge key | `<<: *base` | `the merge key <<` |
| Tag | `!!str 1`, `!x a` | `the tag '!!str'`, `the tag '!x'` |
| Explicit key | `? name` | `an explicit key` |
| Empty key | `: a` | `an empty key` |
| Scalar key that reads as a number, boolean or null | `1: a`, `true: a` | `the non-string key 1`, `the non-string key true` |
| Collection as a key | `[a]: b` | `a collection as a key` |
| Flow collection spread over lines | `tags: [a,` then `  b]` | `a flow collection spread over lines` |
| Collection inside a flow collection | `a: [[1]]`, `a: [b: c]` | `a collection inside a flow collection` |
| Flow collection as the entire block | `{name: a}` | `a flow collection as the block` |
| Block scalar indentation indicator | `text: |2` | `a block scalar indentation indicator` |
| Block sequence item that is a block sequence | `- - a` | `a block sequence as an item of a block sequence` |
| Escape above Unicode's last code point | `a: "\U00110000"` | `an escape that names no Unicode character` |

These characters can still occur as text where YAML treats them as text: `50%`, `b&c`, `2*3`, `wow!`,
`"<<"` as a key, and `<<` as a value. `---` in a value is text; the closing delimiter itself ends the block.
A question mark within a plain scalar in a flow sequence, such as `[what?]`, is text.

## Syntax Errors

Malformed syntax is also `LC202`. Its main message is `frontmatter is not valid YAML`. Lorecraft labels the
document line to fix and gives help for a recognized error. An unclosed quote is reported where it opens. Labels and
help for the recognized kinds are:

| Error | Label | Help |
|---|---|---|
| `: ` inside a plain value | ``this value holds `: ` `` | Quote the value, with an example |
| Key indented under a text value | `` `child` is indented under `parent`, whose value is text `` | Align it with the key it belongs beside |
| Line aligned with no key or item | `this line's indentation matches no key or item above it` | Indent it like the keys or items it belongs with |
| Line that is neither key nor item | ``this line is not `key: value` or `- item` `` | Add `: ` after the key, or quote a value that runs on |
| Unclosed quote | `this quote is never closed` | Close it on the line it continues to, or remove it |
| Text after a closing quote | `text follows the closing quote` | Put the whole value inside the quotes |
| Text after a flow collection, as in `a: [b, c] d` | `` text follows the closing `]` `` (`}` for a mapping) | Move the text inside the brackets, or quote the whole value |
| Closing bracket that closes nothing, as in `a: ]` | `` this `]` closes nothing `` (`}` likewise) | Remove it, or quote the value |
| Tab used to indent | `a tab indents this line` | Indent with spaces |
| U+0085, U+2028 or U+2029 outside quotes; `name: guide␅type: rule` (`␅` = U+0085) | `the block holds U+0085, which is not a line break here` (with its code point) | Use a line feed, or remove it |
| Invalid `\q` escape in double quotes | `` `\q` is not an escape `` | Write `\\` for a backslash, or use single quotes |
| Backslash before U+0085, U+2028 or U+2029 in double quotes | `` `\` before U+0085 is not an escape `` (with its code point) | Write `\\` for a backslash, or use single quotes |
| Character that cannot start a plain value | `` a plain value cannot start with `@` `` (for `@`) | Quote the value |
| Control character | `the block holds the control character U+0007` (with its code point) | Remove it |

A malformed anchor, alias or tag is named as a refusal without help. An error no recognized kind matches gets the label
`the block cannot be read from this line on`, without parser wording or help.

## Repeated Keys

`LC205 duplicate-key` reports each later occurrence of a key in one mapping, at any depth. It covers block
and flow mappings, including mappings in list items. The finding is on the later key's document line, labelled
`written again here`, and points to the first occurrence with `first written here` when it is on another
line. On a single-line flow mapping, only `written again here` appears.

The block still decodes, using the value written last, so other fields can be checked. A key written three
times produces two findings, both pointing to the first. The same name in separate mappings is not a repeat.
When another later value replaces a reported value, a note at the last occurrence says
`the value written last is the one read`.

## References

- [cli-check](cli-check.md) - Related: the command that reports these findings
- [spec-structure-frontmatter](spec-structure-frontmatter.md) - Related: structure schemas applied after decoding
- [adr-019](../arch/adr-019-frontmatter-format.md) - Source: the format decision
- [adr-017](../arch/adr-017-yaml-parser.md) - Source: the parser decision

## Code References

- `src/lorecraft/project/syntax/frontmatter.py` - Decodes the frontmatter block and records refused constructs and repeated keys
- `src/lorecraft/yaml/syntax_error.py` - Describes syntax and character errors
- `src/lorecraft/rules/frontmatter/invalid_yaml.py` - Reports `LC202`
- `src/lorecraft/rules/frontmatter/duplicate_key.py` - Reports `LC205`
