---
name: "LC004-unusable-structure-file"
description: "A structure file follows the structure format and states rules that cannot be applied"
code: "LC004"
since: "0.3.0"
---

# unusable-structure-file (LC004)

A structure file follows the structure format and states rules that cannot be applied.

## What it does

Checks for structure files that follow the structure format and still cannot be used, because a rule they state
contradicts another, repeats itself, or cannot be applied: an outline or a forbidden list that names a section
twice, a forbidden section the outline names, two `any` runs side by side, a title pattern that does not compile,
or a frontmatter schema that is invalid, carries `$id`, names another dialect, holds a `$ref` that does not
resolve inside it or states no object type. Such a file is reported once, at the file, and every document its
meta spec governs is listed as skipped in coverage, with no rule run over it: a document that was not checked is
never reported as clean. Every document the file does not govern is checked as if the file were fixed.

The message says which case it is, and the note under it names what is wrong: the sections, the pattern or the
problem the JSON Schema meta-schema found. Each case is explained below, with its fix.

It has no level, so no configuration turns it off, and it is always reported as an error.

## Why is this bad?

Until the file is fixed, the documents it governs are not checked, so a violation in them goes unreported and an
agent loads them unreviewed.

## A section named twice in the outline

`docs/__meta__/guide.spec.json`, naming `Overview` twice:

```json
{
  "outline": [
    {"section": "Overview"},
    {"section": "Details"},
    {"section": "Overview"}
  ]
}
```

A document could never hold to it. Name each section once:

```json
{
  "outline": [
    {"section": "Overview"},
    {"section": "Details"}
  ]
}
```

## A section forbidden twice

`docs/__meta__/guide.spec.json`, forbidding `Draft` twice:

```json
{
  "forbidden": ["Draft", "Notes", "Draft"]
}
```

Forbid each section once:

```json
{
  "forbidden": ["Draft", "Notes"]
}
```

## A section both in the outline and forbidden

`docs/__meta__/guide.spec.json`, requiring and forbidding `Overview`, so no document could hold to both:

```json
{
  "outline": [{"section": "Overview"}],
  "forbidden": ["Overview"]
}
```

Keep each section in the outline or in the forbidden list, not both:

```json
{
  "outline": [{"section": "Overview"}],
  "forbidden": ["Draft"]
}
```

## Two `any` runs side by side

`docs/__meta__/guide.spec.json`, with two runs in a row. Two runs side by side match exactly what one run
matches, so the outline would mean something other than what it says:

```json
{
  "outline": [
    {"any": true},
    {"any": true, "words": 200}
  ]
}
```

State one run, with the cap the two together were meant to carry:

```json
{
  "outline": [
    {"any": true, "words": 200}
  ]
}
```

## A title pattern that is not a regular expression

`docs/__meta__/guide.spec.json`, with an unclosed bracket in `title.pattern`:

```json
{
  "title": {"pattern": "[A-Z"}
}
```

Write a pattern that compiles:

```json
{
  "title": {"pattern": "^[A-Z]"}
}
```

## A frontmatter schema that is not a valid JSON Schema

`docs/__meta__/guide.spec.json`, with `required` holding a string where a list is due. The `frontmatter` key
must be a valid JSON Schema of the 2020-12 dialect:

```json
{
  "frontmatter": {"type": "object", "required": "name"}
}
```

Write the keyword as the dialect defines it:

```json
{
  "frontmatter": {"type": "object", "required": ["name"]}
}
```

## A frontmatter schema that carries `$id`

`docs/__meta__/guide.spec.json`, with an `$id`, in the schema or in one inside it, which would make it a
schema resource of its own that nothing can reach:

```json
{
  "frontmatter": {
    "$id": "https://example.com/guide",
    "type": "object"
  }
}
```

Leave `$id` out:

```json
{
  "frontmatter": {"type": "object"}
}
```

## A frontmatter schema in another dialect

`docs/__meta__/guide.spec.json`, written in draft-07. A frontmatter schema, or a schema inside it, that sets
`$schema` to anything but the 2020-12 dialect is refused, since that is the only one it is written in:

```json
{
  "frontmatter": {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object"
  }
}
```

Name the 2020-12 dialect, or leave `$schema` out:

```json
{
  "frontmatter": {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object"
  }
}
```

## A frontmatter schema with a `$ref` that does not resolve

`docs/__meta__/guide.spec.json`, with a `$ref` to a definition the schema does not hold. A `$ref` must point
at a location inside the schema: a reference to another file or URL is never fetched:

```json
{
  "frontmatter": {
    "type": "object",
    "properties": {"name": {"$ref": "#/$defs/name"}}
  }
}
```

Define what the reference names:

```json
{
  "frontmatter": {
    "type": "object",
    "properties": {"name": {"$ref": "#/$defs/name"}},
    "$defs": {"name": {"type": "string"}}
  }
}
```

## A frontmatter schema that states no object type

`docs/__meta__/guide.spec.json`, with a root that states properties but no type. A document's frontmatter is
always a mapping, so a schema that does not say so would accept values no document can hold:

```json
{
  "frontmatter": {
    "properties": {"name": {"type": "string"}}
  }
}
```

State the type at the root:

```json
{
  "frontmatter": {
    "type": "object",
    "properties": {"name": {"type": "string"}}
  }
}
```
