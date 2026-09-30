---
name: "cli-check-skills"
description: "lorecraft check skills: validating the frontmatter of each agent skill's SKILL.md against the Agent Skills specification, the name-matches-directory rule, how a skill is named on the command line, and the rule identifiers it reports. Load when a skill finding needs explaining, when running the skill check on its own, or when a skill is not checked"
type: "feature"
status: "experimental"
components: "module:lorecraft.cli.commands.check.skills,module:lorecraft.checks.skill,module:lorecraft.project.schemas.skill_frontmatter,module:lorecraft.project.skill"
---

# `lorecraft check skills`

## Summary

`lorecraft check skills` validates the YAML frontmatter that opens each skill's `SKILL.md` against the
[Agent Skills specification](https://agentskills.io/specification), and checks that the frontmatter `name`
equals the name of the skill's directory. It reads the skills the [workspace](workspace.md) lists, through
whichever link an agent reaches them by. It is also one of the checks a bare `lorecraft check` runs.

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

- Only the frontmatter is checked. The length of the body and the links in it are not.
- A skill entry or a `SKILL.md` that is a symlink is read where it leads. One whose link dangles or leads outside
  the repository is not a skill, and is not reported.
- Without `--root`, the root is still found by its `docs/__meta__/`, so a repository that has skills and no
  specifications needs `--root`.
- Run on its own, the check reads no document, so it accepts a root whose `docs/` or `docs/__meta__/` is a
  symlink, which a check over documents refuses.

## Findings

A finding is reported at the skill's `SKILL.md`, as listed under the skills directory, on the line of the field
it concerns, or on line 1 when the field is absent, the key is not a string, or the whole block is at fault. A
skill whose frontmatter is missing, unparseable or undecodable reports that one finding and nothing else.

`name` is compared as written, with no Unicode normalisation, so a full-width letter is a `skill.name` finding.
An optional field written with no value, such as `license:`, is read as absent and accepted.

| Rule | Reported when |
|------|---------------|
| `skill.frontmatter-missing` | The `SKILL.md` does not open with a `---` delimited block |
| `skill.frontmatter-unparseable` | The block is not valid YAML, or is not a mapping |
| `skill.undecodable` | The file is not valid UTF-8 |
| `skill.name-matches-directory` | `name` is not the name of the skill's directory |
| `skill.<field>` | The specification rejects that field, or requires it and it is absent |
| `skill.unknown-field` | A field the specification does not define, such as `model`, or a key that is not a string, such as `123` |

## References

- [cli-check](cli-check.md) - Base: root discovery, output and exit status
- [workspace](workspace.md) - Dependency: the snapshot the skills are read from
- [cli-inspect](cli-inspect.md) - Related: shows the skills this check reads and the agents that read them

## Code References

- `src/lorecraft/cli/commands/check/skills.py` - Declares the command and registers the check with the group
- `src/lorecraft/checks/skill.py` - The check of one skill's frontmatter
- `src/lorecraft/project/schemas/skill_frontmatter.py` - Declares the specification's fields and their limits
- `src/lorecraft/project/skill/` - Finds the skills and reads a `SKILL.md`
