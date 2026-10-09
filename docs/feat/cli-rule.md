---
name: "cli-rule"
description: "lorecraft rule: the rulebook on the command line, a rule's page by code, name or alias code, and the listing of every rule in code order, the same text as docs/rulebook/. Load when a diagnostic prints a code and you want to know what it means and how to fix it, looking up a rule from an upstream linter, or listing the rules"
type: "feature"
status: "experimental"
components: "module:lorecraft.cli,module:lorecraft.rules"
---

# `lorecraft rule`

## Summary

`lorecraft rule` prints what a rule checks, why it matters and how to fix it, for a user who has only the installed
package. `lorecraft rule OUT006` prints the page of that rule, and a bare `lorecraft rule` lists every rule in code
order. The page is the one in `docs/rulebook/`, rendered by the same function from the rule's docstring.

## Table of Contents

1. [Key Concepts](#key-concepts)
2. [Configuration](#configuration)
3. [Usage](#usage)
4. [Limitations](#limitations)
5. [References](#references)
6. [Code References](#code-references)

## Key Concepts

- **Rulebook**: The reference manual of the rules, one page per code, in `docs/rulebook/` of this repository and in
  this command. Every word of it is generated from the rules' classes, and a page is fixed in the rule's docstring.
- **Page**: What the rulebook says about one rule: a frontmatter of what the rule declares, a title, and the
  sections of its docstring: *What it does*, *Why is this bad?*, *Example*, *Use instead*, and *Known problems*
  and *Deviations from upstream* when it has them.
- **Alias code**: An upstream linter's code for a rule Lorecraft absorbed, such as a markdown linter's. The rule's
  code is always Lorecraft's; the page of the rule lists its alias codes, and the command finds the page by one.
- **Removed rule**: A retired code, which has a page that gives the release that removed it and what replaced it.

## Configuration

| Argument or option | Default | Description |
|--------------------|---------|-------------|
| `[RULE]`           | none: list every rule | A rule by its code, its name or an alias code, such as `OUT006` or `missing-section` |

The rules are part of the package, so the command reads no workspace and takes no `--root`. A code, a name and an
alias code are matched exactly, with their case.

## Usage

```bash
# Every rule in code order
lorecraft rule

# A rule's page, by its code or by its name
lorecraft rule OUT004
lorecraft rule empty-section
```

### Output

The listing is a line per rule on stdout: the code, the name, the default level and the condition the rule reports.
A removed rule shows `removed` in place of a level, and an engine condition the `error` it is always reported at,
since it has no level:

```text
FM007    unknown-field            warn   A frontmatter holds a field its schema does not define.
LC001    invalid-utf8             error  A file is not valid UTF-8.
OUT004   empty-section            deny   A section holds no content, under a structure specification that forbids empty sections.
```

A page is Markdown on stdout, the file `docs/rulebook/<code>-<name>.md`, so a reader without the repository reads
the same text. This is the start of one, with its sections cut at `…`:

```text
---
name: "OUT004-empty-section"
description: "A section holds no content, under a structure specification that forbids empty sections"
code: "OUT004"
since: "0.3.0"
---

# empty-section (OUT004)

A section holds no content, under a structure specification that forbids empty sections.

## What it does

Checks for headings whose section holds nothing, …
```

### Exit Status

| Code | Meaning |
|------|---------|
| `0`  | The page or the listing was printed |
| `2`  | No rule has the code, name or alias code typed, which is printed on stderr, or a usage error |

## Limitations

- The command finds a rule by exact match: it offers no search and no suggestion for a mistyped code.
- It prints the page of one rule at a time. A group's prefix, such as `OUT`, is a selector of
  [check](cli-check.md#selecting-rules) and names no page.

## References

- [cli](cli.md) - Base: the command line and the options every command shares
- [cli-check](cli-check.md) - Related: reports the diagnostics whose codes this command explains

## Code References

- `src/lorecraft/cli/commands/rule.py` - Declares the command and its argument
- `src/lorecraft/cli/rule_run.py` - Looks the rule up in the registry
- `src/lorecraft/cli/rulebook.py` - Renders a rule's page and the listing, for this command and for the pages in `docs/rulebook/`
- `src/lorecraft/rules/registry.py` - The one list of rules, found by code, name or alias code
- `docs/rulebook/` - The generated pages, one per code
