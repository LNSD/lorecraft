---
name: "cli-check-skills"
description: "lorecraft check skills: validating the frontmatter of each agent skill's SKILL.md against the Agent Skills specification, the name-matches-directory rule, duplicate keys, the 500-line budget on a SKILL.md, links in any of a skill's Markdown files that are absolute, name a heading the file lacks, leave the skill or name nothing in it, and the skill-root resolution they follow, the files a skill links in through `metadata`, symlinks in the skill layout that lead outside the repository, how a skill is named on the command line, and the rule identifiers it reports. Load when a skill finding needs explaining, when running the skill check on its own, or when a skill is not checked"
type: "feature"
status: "experimental"
components: "module:lorecraft.cli,module:lorecraft.checks,module:lorecraft.project"
---

# `lorecraft check skills`

## Summary

`lorecraft check skills` holds each `SKILL.md` to the
[Agent Skills specification](https://agentskills.io/specification): its frontmatter, a `name` matching the
directory agents list, through any symlink, and at most 500 lines. It reports a link in any skill file that is
absolute, names a missing heading, leaves the skill or names nothing, a `metadata` path repeating a file name,
missing, or outside what it reads, and a symlink leaving the repository. It reads the
[workspace](workspace.md)'s skills; a bare `lorecraft check` runs it too.

## Table of Contents

1. [Key Concepts](#key-concepts)
2. [Configuration](#configuration)
3. [Usage](#usage)
4. [Limitations](#limitations)
5. [Findings](#findings)
6. [References](#references)
7. [Code References](#code-references)

## Key Concepts

- **Skill**: A directory directly inside an agent's skills directory, such as `.agents/skills/review/`, or one
  named on the command line, or directly inside one, that holds a `SKILL.md`. The entry may be a symlink to a directory elsewhere in the
  repository, never outside it.
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
| `PATHS...`         | every skill an agent reads | The skills to check, each by a skill directory, a directory of skills, or a `SKILL.md`, relative to the working directory |
| `--root <path>`    | nearest parent holding `docs/__meta__/` | The repository root, as [cli-check](cli-check.md#root-discovery) describes |
| `--format <text\|json>` | `text` | The output format, as [cli-check](cli-check.md#output) describes |

A path names a skill directory, a directory of skills or a `SKILL.md`, through a link or not. A skills directory
an agent reads, such as `.claude/skills`, selects every skill listed there, reported under the resolved directory,
possibly none; an entry of one selects that entry alone, even when it links to another. Any other directory is one
skill when a `SKILL.md` is at its root, and otherwise holds each directory directly in it that has one. Its skills
are named as the path spells them: `skills/review` is checked as `skills/review`, not as the entry linking there.
The file a linked `SKILL.md` leads to names that skill too. Under the root the path is resolved in the
[snapshot](workspace.md#one-snapshot), `..` by its spelling; above it a link is followed on disk. A path leading
to no skill and no symlink leaving the repository refuses the run.

## Usage

```bash
# Check every skill
lorecraft check skills

# Check one skill just written
lorecraft check skills .agents/skills/review

# Check its SKILL.md alone
lorecraft check skills .agents/skills/review/SKILL.md

# Check the skills kept in skills/, which no agent reads
lorecraft check skills skills
```

```text
.agents/skills/review/SKILL.md:2: [skill.name-matches-directory] `name` is 'audit'; expected 'review', the name of the skill directory
checked 1 skill(s), 1 finding(s)
```

A skill named by its directory, by a skills directory, or by no path is checked whole. One named by its `SKILL.md`,
directly, through a link, or by the file a linked `SKILL.md` leads to, has that file checked alone: its frontmatter,
its length, its links and its `metadata`. No resource or symlink inside the skill is looked at, yet a link to a
resource still names something in the skill. A skill named both ways in one run is checked whole, once, where first
named.

The output and the exit status are the ones every check shares: see [Output](cli-check.md#output) and
[Exit Status](cli-check.md#exit-status). The specification governs every skill, so none is ever listed as
ungoverned, and `ungoverned` is always empty in the JSON report.

## Limitations

- A fragment after a path, such as `guide.md#usage`, is not checked against the file it names.
- An HTML heading (`<h2>`) has no anchor.
- Only the `metadata` subkeys `references`, `scripts` and `assets` are read.
- A linked skill entry or `SKILL.md` is read where it leads; one that dangles is skipped silently.
- A repository with skills and no `docs/__meta__/` needs `--root`.
- The root is never read for skills, which would read the whole repository.
- A `metadata` path is judged by what the run reads: naming `skills/gamma` or `skills` can judge a path into a
  sibling skill outside the scope or missing.
- A key repeated inside a nested mapping such as `metadata` is not reported as repeated.
- A field supplied only through a YAML merge (`<<`) has no line of its own, so a finding about it is on line 1.
- A key written as a YAML alias (`*k`) is placed on its anchor's line, so a finding about it is there.
- Run alone, it accepts a linked `docs/` or `docs/__meta__/`, which a check over documents refuses.

## Findings

A finding is reported in the file it is about, named under the skills directory or the path given: a link
finding on the link's line, in the `SKILL.md` or the resource holding it. A frontmatter finding is at the
`SKILL.md`, on the line of the field it concerns, on the line the YAML parser stopped at when the block does not
parse, or on line 1 when the field is absent or the whole block is at fault. A
missing or unparseable frontmatter is one finding, and the links are still checked; a `SKILL.md` that is not
UTF-8 reports that alone. A `skill.lines-budget` finding is on line 1, after the frontmatter findings and before
the link findings. A skill's `SKILL.md` findings come first, then each resource's, by path, then line.

`name` is compared as written, with no Unicode normalisation, so a full-width letter is a `skill.name` finding.
An optional field written with no value, such as `license:`, is read as absent and accepted. The name is
compared with the directory agents list, through any symlink, then the specification applied, then repeated keys
reported, as the [frontmatter check](cli-check-frontmatter.md#findings) does. Every message is Lorecraft's own,
whatever version of the library validating the fields is installed.

A `skill.metadata-*` finding is on the line of the `metadata` key, after the `SKILL.md`'s link findings. Within a
subkey, repeated file names come first, then missing paths, then paths outside the scope, each in the order written
and once per occurrence.

A top-level key written again is a `skill.duplicate-key` finding, on the line of each occurrence after the first,
and it suppresses no other finding; any other finding about that key is on the line of its last occurrence. The
[frontmatter check](cli-check-frontmatter.md#findings) states the rule in full, merges included.

| Rule | Reported when |
|------|---------------|
| `skill.frontmatter-missing` | The `SKILL.md` does not open with a `---` delimited block |
| `skill.frontmatter-unparseable` | The block is not valid YAML, or is not a mapping, or writes a key, at any depth, that is not a string, such as `1`, `true` or `null`, reported on the key's line; a quoted key such as `'1'` is a string |
| `skill.undecodable` | The `SKILL.md` or a resource is not valid UTF-8; a resource reports it alone, and its links are not checked |
| `skill.name-matches-directory` | `name` is not the name of the directory an agent lists the skill by, or the path given names it by, through any symlink: for `.agents/skills/bar -> ../../skills/foo`, `name` must be `bar`. Where a link leads plays no part in the verdict; when its name differs, a note on the finding names it, root-relative, or as the repository root |
| `skill.duplicate-key` | A top-level key is written again; the message gives the line of the first occurrence |
| `skill.<field>` | The specification rejects that field, or requires it and it is absent |
| `skill.unknown-field` | A field the specification does not define, such as `model` |
| `skill.frontmatter` | The specification rejects the frontmatter as a whole |
| `skill.lines-budget` | The `SKILL.md` holds more than 500 lines, frontmatter included, each ended by a newline as finding lines are numbered, where a final newline adds no line; the message gives the count and the budget, and a help note says how to fix it. A resource has no budget |
| `skill.link-absolute` | A link or image in the `SKILL.md` or a resource has a destination that starts with `/`; the message shows the link decoded, and a help note says how to fix it |
| `skill.link-fragment` | A link in the `SKILL.md` or a resource whose destination is only a `#fragment` names no heading of the file holding it, at any depth, by GitHub's anchors, regardless of case; the message shows the link decoded, and a bare `#` is not reported |
| `skill.link-escapes` | A relative link or image in the `SKILL.md` or a resource, its path percent-decoded and normalised lexically, climbs above the skill root, whatever directory the skill is in; no symlink is followed, the fragment and the query are ignored, the message shows the link decoded, and a help note says how to fix it |
| `skill.link-broken` | A relative link or image in the `SKILL.md` or a resource stays inside the skill, yet its path, read from the skill root as an agent reaches it, leads to no file or directory in the snapshot, through any symlink, and is no linked-in file; the fragment and the query are ignored, the message shows the link decoded, and a help note says how to fix it. A linked-in file that is missing is `skill.metadata-missing-file`'s alone. Not judged at all when the `SKILL.md` frontmatter is missing, unparseable or not a mapping, or the `SKILL.md` is not UTF-8: which files `metadata` links in is then unknown |
| `skill.metadata-duplicate-name` | A path under a `metadata` subkey has the file name of an earlier one, so both link in as one path; the message names both |
| `skill.metadata-missing-file` | A listed path in scope, as the [workspace declares it](workspace.md#one-snapshot), leads to no regular file in the snapshot: nothing is there, not even its directory, a directory is, or a link dangles, leaves the repository or reaches a file lorecraft does not read |
| `skill.metadata-outside-scope` | A listed path is in a directory the command does not read, or is absolute or climbs with `..` |
| `skill.symlink-outside` | A skills directory an agent declares, a path given, an entry in either, its `SKILL.md` or the one at the root of a directory given, or a file or directory inside a skill is a symlink whose chain leaves the repository: a link targets a path outside it, or a `..` climbs above the root. Judged from the link targets the snapshot recorded; nothing outside the root is read. On line 1 at the symlink, named where an agent reaches it, with a note naming the link the chain leaves through and its target, and a help note says how to fix it. One not inside a skill is no skill: it is reported first, by path, whichever skills are selected, and counts no skill; one inside a skill comes after that skill's resources. A chain is judged by the resolved path each step reaches, as the operating system resolves it, so `tmp/../../..` leaves as surely as `../..`. A link that dangles or loops inside the repository is not reported |

## References

- [cli-check](cli-check.md) - Base: root discovery, output and exit status
- [workspace](workspace.md) - Dependency: the snapshot the skills are read from
- [cli-inspect](cli-inspect.md) - Related: shows the skills this check reads and the agents that read them

## Code References

- `src/lorecraft/cli/commands/check/skills.py` - Declares the command and registers the check with the group
- `src/lorecraft/cli/check_run.py` - Selects the skills a run checks, merging a skill named twice, and prints the report
- `src/lorecraft/cli/select.py` - Maps a path argument onto the skills it names, or refuses it
- `src/lorecraft/checks/skill.py` - The check of one skill's frontmatter
- `src/lorecraft/checks/skill_length.py` - Holds a `SKILL.md` to the 500-line budget
- `src/lorecraft/checks/frontmatter_duplicate.py` - Reports a key written twice, for this check and the frontmatter check
- `src/lorecraft/checks/frontmatter_problem.py` - Names the rule a schema problem breaks and the line it is reported on, for this check and the frontmatter check
- `src/lorecraft/checks/skill_link.py` - Reports an absolute link, a dangling fragment link, or a link leaving the skill or naming nothing in it
- `src/lorecraft/checks/run.py` - Reads each skill and its resources, looks up each path a link names, and locates each finding in its file
- `src/lorecraft/checks/skill_metadata.py` - Reports a duplicate, missing or out-of-scope file in a skill's `metadata`
- `src/lorecraft/checks/skill_symlink.py` - Reports a symlink of the skill layout that leads outside the repository
- `src/lorecraft/project/schemas/skill.py` - Holds a frontmatter to the specification, in Lorecraft's words
- `src/lorecraft/project/schemas/skill_frontmatter.py` - Declares the specification's fields and their limits
- `src/lorecraft/project/schemas/frontmatter_problem.py` - The problem shape both frontmatter schemas report in
- `src/lorecraft/project/skill/` - Finds the skills, and the symlinks leading outside, and reads a `SKILL.md`
- `src/lorecraft/project/syntax/lines.py` - Counts the lines of a `SKILL.md`
