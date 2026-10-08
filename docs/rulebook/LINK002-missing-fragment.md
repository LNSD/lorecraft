---
name: "LINK002-missing-fragment"
description: "A link to a heading of the same Markdown file names a heading the file does not have"
code: "LINK002"
since: "0.3.0"
---

# missing-fragment (LINK002)

A link to a heading of the same Markdown file names a heading the file does not have.

## What it does

Checks for links and images whose destination is a fragment alone, such as `#usage`, naming none of the
headings of the file that holds them, in every Markdown file the checks read: a document whose corpus states a
structure specification, a skill's `SKILL.md` and each Markdown file inside the skill. No specification key
states the rule: every such file is held to it.

A fragment names a heading by its anchor, as GitHub derives it, whatever the case it is written in: `#Usage`
names `## Usage`. A repeated heading's anchors are numbered, so a second `## Usage` is `#usage-1`. A bare `#`
names no heading, so it is not reported. A fragment after a path, such as `setup.md#usage`, names a heading of
another file, which this rule does not check.

## Why is this bad?

A link to a heading that does not exist goes nowhere: an agent that follows it lands at the top of the file, or
nowhere, and reads the wrong part of it, or none.

## Example

`docs/guide/setup.md`:

```markdown
# Setup

Every option is listed under [configuration](#configuration).

## Options
```

## Use instead

Name the heading the file has:

```markdown
# Setup

Every option is listed under [options](#options).

## Options
```
