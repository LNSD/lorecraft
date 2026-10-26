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
alias code are matched exactly, with their case; surrounding whitespace is not removed. A key may name a rule in
service, a removed rule or an engine condition. An alias code is valid exactly when a rule declares it; aliases
have no separate required shape. `[RULE]` is validated while the command line is read, before the listing or a
page is printed.

## Usage

```bash
# Every rule in code order
lorecraft rule

# A rule's page, by its code or by its name
lorecraft rule OUT004
lorecraft rule empty-section

# The page for paths that cannot be read, by code or name
lorecraft rule LC002
lorecraft rule unreadable-path
```

### Output

The listing is a line per rule on stdout: the code, the name, the default level and the condition the rule reports.
A removed rule shows `removed` in place of a level, and an engine condition the `error` it is always reported at,
since it has no level. The listing includes `LC001` through `LC004`; this excerpt shows entries from it:

```text
LC207    unknown-field             warn   A frontmatter holds a field its schema does not define.
LC001    invalid-utf8              error  A file is not valid UTF-8.
LC002    unreadable-path           error  A path cannot be read.
LC003    malformed-structure-file  error  A structure file does not follow the structure format, or states no rule.
LC004    unusable-structure-file   error  A structure file follows the structure format and states rules that cannot be applied.
OUT004   empty-section             deny   A section holds no content, under a structure file that forbids empty sections.
```

### Default Levels

Every rule in the listing has the default level shown here. `allow` rules do not appear because they are not
run. `LC001`–`LC004` are engine conditions, not rules; they are always reported as errors and have no level.

| Default level | Rule codes |
|---------------|------------|
| `deny` | `LC201`, `LC202`, `LC203`, `LC204`, `LC205`, `LC206`, `LC208`, `LC209`, `LC210`, `LC213`, `LC214`, `LC102`, `LEN001`, `LEN002`, `LEN003`, `LEN004`, `LEN005`, `LINK001`, `LINK002`, `LINK003`, `LINK004`, `OUT001`, `OUT002`, `OUT003`, `OUT004`, `OUT005`, `OUT006`, `OUT007`, `OUT008`, `OUT009` |
| `warn` | `LC207`, `LC211`, `LC212`, `LINK005`, `LINK006`, `LINK007` |

The `LC002` page covers unreadable structure files, unlistable corpus and skills directories, skills
that cannot be listed or resolved, and `SKILL.md` links that cannot be followed. A regular `SKILL.md` whose
contents cannot be read still stops `check` with exit `2`.
The `LC003` page covers format errors and a file that states no rule. The `LC004` page explains each kind of
unusable rule with its fix.

A page is Markdown on stdout, the file `docs/rulebook/<code>-<name>.md`, so a reader without the repository reads
the same text. This is the start of one, with its sections cut at `…`:

```text
---
name: "OUT004-empty-section"
description: "A section holds no content, under a structure file that forbids empty sections"
code: "OUT004"
since: "0.3.0"
---

# empty-section (OUT004)

A section holds no content, under a structure file that forbids empty sections.

## What it does

Checks for headings whose section holds nothing, …
```

### Exit Status

| Code | Meaning |
|------|---------|
| `0`  | The page or the listing was printed |
| `2`  | A malformed or unknown code, name or alias reports a usage error naming `[RULE]` on stderr, as [cli](cli.md) describes |

## Limitations

- The command finds a rule by exact match: it offers no search and no suggestion for a mistyped code.
- It prints the page of one rule at a time. A code range groups rules for reading but names no page;
  [check](cli-check.md#selecting-rules) accepts only `ALL`, a full rule code or an alias code.

## References

- [cli](cli.md) - Base: the command line and the options every command shares
- [cli-check](cli-check.md) - Related: reports the diagnostics whose codes this command explains

## Code References

- `src/lorecraft/cli/commands/rule.py` - Declares the command and parses `[RULE]`
- `src/lorecraft/cli/rule_run.py` - Loads rules and prints the page or listing
- `src/lorecraft/cli/rule_arguments.py` - `RuleKey.parse` validates rule keys against the rule index
- `src/lorecraft/cli/rulebook.py` - Renders a rule's page and the listing, for this command and for the pages in `docs/rulebook/`
- `src/lorecraft/rules/registry.py` - The only source of rules, found by code, name or alias code
- `docs/rulebook/` - The generated pages, one per code
