---
name: "cli-check-skills"
description: "lorecraft check skills: validating the frontmatter of each agent skill's SKILL.md against the Agent Skills specification, the name-matches-directory rule, duplicate keys, the 500-line budget on a SKILL.md, absolute and dangling fragment links in the body, links that leave the skill or name nothing in it from any of its Markdown files and the skill-root resolution they follow, the files a skill links in through `metadata`, how a skill is named on the command line, and the rule identifiers it reports. Load when a skill finding needs explaining, when running the skill check on its own, or when a skill is not checked"
type: "feature"
status: "experimental"
components: "module:lorecraft.cli.commands.check.skills,module:lorecraft.checks.skill,module:lorecraft.checks.frontmatter_duplicate,module:lorecraft.checks.skill_length,module:lorecraft.checks.skill_link,module:lorecraft.checks.skill_metadata,module:lorecraft.checks.run,module:lorecraft.project.schemas.skill,module:lorecraft.project.schemas.skill_frontmatter,module:lorecraft.project.schemas.frontmatter_problem,module:lorecraft.project.skill,module:lorecraft.project.syntax.lines"
---

# `lorecraft check skills`

## Summary

`lorecraft check skills` holds each skill's `SKILL.md` to the
[Agent Skills specification](https://agentskills.io/specification): its frontmatter, a `name` matching its
directory, and at most 500 lines. It reports a link in a skill Markdown file that leaves the skill or names
nothing there, absolute and dangling fragment links in the body, and a `metadata` path that repeats a file name,
is missing or lies outside what it reads. It reads the skills the [workspace](workspace.md) lists; a bare
`lorecraft check` runs it too.

## Table of Contents

1. [Key Concepts](#key-concepts)
2. [Configuration](#configuration)
3. [Usage](#usage)
4. [Limitations](#limitations)
5. [Findings](#findings)
6. [References](#references)
7. [Code References](#code-references)

## Key Concepts

- **Skill**: A directory directly inside an agent's skills directory, such as `.agents/skills/review/`, that
  holds a `SKILL.md`. The entry may be a symlink to a directory elsewhere in the repository.
- **Resource**: A Markdown file inside a skill other than its top-level `SKILL.md`, at any depth, such as
  `references/guide.md`. It is named under the skill's directory, through any symlink on the way.
- **Skill root**: A relative link in any Markdown file of a skill is read from the skill's directory, as the
  specification has it, not from the file holding it: from `references/guide.md`, the entry file is `SKILL.md`,
  and `../SKILL.md` leaves the skill.
- **Linked-in file**: A repository file a `metadata` subkey lists, which lands in the skill at
  `<subkey>/<file name>`: `references: docs/code/logging.md` is `references/logging.md`. A link to it names
  something in the skill, whatever the skill's directory holds.
- **Frontmatter**: The YAML mapping between two `---` lines that opens a `SKILL.md`.
- **Specification field**: One of the six fields the specification defines: `name`, `description`, `license`,
  `compatibility`, `metadata` and `allowed-tools`. No other field is accepted, whichever agent reads the skill.

## Configuration

| Argument or option | Default | Description |
|--------------------|---------|-------------|
| `PATHS...`         | every skill | The skills to check, each by its directory or its `SKILL.md`, relative to the working directory |
| `--root <path>`    | nearest parent holding `docs/__meta__/` | The repository root, as [cli-check](cli-check.md#root-discovery) describes |
| `--format <text\|json>` | `text` | The output format, as [cli-check](cli-check.md#output) describes |

A path names a skill through a link or not: a skill kept in `skills/review/` and linked from
`.agents/skills/review` is named by either, and a directory two entries link to selects both. A `SKILL.md` that
is itself a link is named by the file it leads to as well. Under the repository root the path is
resolved in the [snapshot](workspace.md#one-snapshot), not on disk, so it names what the run reads; `..` is
taken by its spelling. Above the root a link is followed on disk, so the root may be reached through one. A path that leads to no skill the workspace lists refuses the run.

## Usage

```bash
# Check every skill
lorecraft check skills

# Check one skill just written
lorecraft check skills .agents/skills/review
```

```text
.agents/skills/review/SKILL.md:2: [skill.name-matches-directory] `name` is 'audit'; expected 'review', the name of the skill directory
checked 1 skill(s), 1 finding(s)
```

The output and the exit status are the ones every check shares: see [Output](cli-check.md#output) and
[Exit Status](cli-check.md#exit-status). The specification governs every skill, so none is ever listed as
ungoverned, and `ungoverned` is always empty in the JSON report.

## Limitations

- Absolute and bare `#fragment` links are checked in `SKILL.md` only, and a fragment after a path, such as
  `guide.md#usage`, is not checked against the file it names.
- An HTML heading (`<h2>`) has no anchor.
- Only the `metadata` subkeys `references`, `scripts` and `assets` are read.
- A skill entry or `SKILL.md` that is a symlink is read where it leads; one that dangles or leads outside the
  repository is not a skill, and is not reported.
- Without `--root`, the root is found by its `docs/__meta__/`, so a repository with skills and no specifications
  needs `--root`.
- A key repeated inside a nested mapping such as `metadata`, or a non-string key, is not reported as repeated.
- A field supplied only through a YAML merge (`<<`) has no line of its own, so a finding about it is on line 1.
- A key written as a YAML alias (`*k`) is placed on its anchor's line, so a finding about it is there.
- Run on its own, the check reads no document, so it accepts a root whose `docs/` or `docs/__meta__/` is a
  symlink; a check over documents refuses it.

## Findings

A finding is reported in the file it is about, named as an agent reads it, under the skills directory: a link
finding on the link's line, in the `SKILL.md` or the resource holding it. A frontmatter finding is at the
`SKILL.md`, on the line of the field it concerns, on the line the YAML parser stopped at when the block does not
parse, or on line 1 when the field is absent, the key is not a string, or the whole block is at fault. A
missing or unparseable frontmatter is one finding, and the links are still checked; a `SKILL.md` that is not
UTF-8 reports that alone. A `skill.lines-budget` finding is on line 1, after the frontmatter findings and before
the link findings. A skill's `SKILL.md` findings come first, then each resource's, by path, then line.

`name` is compared as written, with no Unicode normalisation, so a full-width letter is a `skill.name` finding.
An optional field written with no value, such as `license:`, is read as absent and accepted. The name is
compared with the directory first, then the specification is applied, then repeated keys are reported, as the
[frontmatter check](cli-check-frontmatter.md#findings) does. Every message is Lorecraft's own, so it does not
change with the version of the library that validates the fields.

A `skill.metadata-*` finding is on the line of the `metadata` key. Within a subkey, repeated file
names come first, then missing paths, then paths outside the scope, each in the order written
and once per occurrence.

A top-level key written again is a `skill.duplicate-key` finding, on the line of each occurrence after the first,
and it suppresses no other finding; any other finding about that key is on the line of its last occurrence. The
[frontmatter check](cli-check-frontmatter.md#findings) states the rule in full, merges included.

| Rule | Reported when |
|------|---------------|
| `skill.frontmatter-missing` | The `SKILL.md` does not open with a `---` delimited block |
| `skill.frontmatter-unparseable` | The block is not valid YAML, or is not a mapping |
| `skill.undecodable` | The `SKILL.md` or a resource is not valid UTF-8; a resource reports it alone, and its links are not checked |
| `skill.name-matches-directory` | `name` is not the name of the skill's directory |
| `skill.duplicate-key` | A top-level key is written again; the message gives the line of the first occurrence |
| `skill.<field>` | The specification rejects that field, or requires it and it is absent |
| `skill.unknown-field` | A field the specification does not define, such as `model`, or a key that is not a string, such as `123` |
| `skill.frontmatter` | The specification rejects the frontmatter as a whole |
| `skill.lines-budget` | The `SKILL.md` holds more than 500 lines, frontmatter included, each ended by a newline as finding lines are numbered, where a final newline adds no line; the message gives the count and the budget, and a help note says how to fix it. A resource has no budget |
| `skill.link-absolute` | A link or image in the body has a destination that starts with `/`; the message shows the link decoded, and a help note says how to fix it |
| `skill.link-fragment` | A link whose destination is only a `#fragment` names no heading of the `SKILL.md`, at any depth, by GitHub's anchors, regardless of case; the message shows the link decoded, and a bare `#` is not reported |
| `skill.link-escapes` | A relative link or image in the `SKILL.md` or a resource, its path percent-decoded and normalised lexically, climbs above the skill root, whatever directory the skill is in; no symlink is followed, the fragment and the query are ignored, the message shows the link decoded, and a help note says how to fix it |
| `skill.link-broken` | A relative link or image in the `SKILL.md` or a resource stays inside the skill, yet its path, read from the skill root as an agent reaches it, leads to no file or directory in the snapshot, through any symlink, and is no linked-in file; the fragment and the query are ignored, the message shows the link decoded, and a help note says how to fix it. A linked-in file that is missing is `skill.metadata-missing-file`'s alone. Not judged at all when the `SKILL.md` frontmatter is missing, unparseable or not a mapping, or the `SKILL.md` is not UTF-8: which files `metadata` links in is then unknown |
| `skill.metadata-duplicate-name` | A path under a `metadata` subkey has the file name of an earlier one, so both link in as one path; the message names both |
| `skill.metadata-missing-file` | A listed path in scope, as the [workspace declares it](workspace.md#one-snapshot), leads to no regular file in the snapshot: nothing is there, not even its directory, a directory is, or a link dangles, leaves the repository or reaches a file lorecraft does not read |
| `skill.metadata-outside-scope` | A listed path is in a directory the command does not read, or is absolute or climbs with `..` |

## References

- [cli-check](cli-check.md) - Base: root discovery, output and exit status
- [workspace](workspace.md) - Dependency: the snapshot the skills are read from
- [cli-inspect](cli-inspect.md) - Related: shows the skills this check reads and the agents that read them

## Code References

- `src/lorecraft/cli/commands/check/skills.py` - Declares the command and registers the check with the group
- `src/lorecraft/checks/skill.py` - The check of one skill's frontmatter
- `src/lorecraft/checks/skill_length.py` - Holds a `SKILL.md` to the 500-line budget
- `src/lorecraft/checks/frontmatter_duplicate.py` - Reports a key written twice, for this check and the frontmatter check
- `src/lorecraft/checks/skill_link.py` - Reports an absolute link, a dangling fragment link, or a link leaving the skill or naming nothing in it
- `src/lorecraft/checks/run.py` - Reads each skill and its resources, looks up each path a link names, and locates each finding in its file
- `src/lorecraft/checks/skill_metadata.py` - Reports a duplicate, missing or out-of-scope file in a skill's `metadata`
- `src/lorecraft/project/schemas/skill.py` - Holds a frontmatter to the specification, in Lorecraft's words
- `src/lorecraft/project/schemas/skill_frontmatter.py` - Declares the specification's fields and their limits
- `src/lorecraft/project/schemas/frontmatter_problem.py` - The problem shape both frontmatter schemas report in
- `src/lorecraft/project/skill/` - Finds the skills and reads a `SKILL.md`
- `src/lorecraft/project/syntax/lines.py` - Counts the lines of a `SKILL.md`
