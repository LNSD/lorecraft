---
name: skills-check
description: Write skills that comply with the Agent Skills specification, and check skills under .agents/skills/ and skills/ against it. Use before creating or editing a SKILL.md or any file in a skill directory, when reviewing a skill change, or before committing one
compatibility: Requires uv to run the script in scripts/; it declares its own dependencies and resolves them on the first run. Nothing is built and no service is contacted.
allowed-tools: Bash(.agents/skills/skills-check/scripts/check_skill.py*) Bash(just check-skills*) Bash(git diff*) Bash(git status*) Bash(git merge-base*) Bash(ls .agents/skills/*) Bash(ls skills/*)
---

# Skills Check

Skills in this repository follow the [Agent Skills specification](https://agentskills.io/specification). This
skill is both paths: **§1-§4 are how to write a skill**, §5-§8 are how to check one. It checks format,
discovery, and structure. It does not check whether the behavior a skill describes is right: that is the
feature docs' job, through `/feat-validate`, and §8 says when to send a skill there.

The specification is the authority. Where this skill and the specification disagree, the specification wins
and this skill has a bug.

## 1. Which kind of skill

A skill's location decides the rules it is held to.

| Location | Kind | Loaded by | Rules |
|---|---|---|---|
| `.agents/skills/<name>/` | Workspace skill | Agents working in this repository (`.claude/skills/` is a symlink to it) | The specification, plus the frontmatter extensions below, and links into the repository |
| `skills/<name>/` | Project skill | Agents in other repositories, after the skill is installed there | The specification only; nothing may depend on this repository's agent or layout |

Every skill here is a workspace skill today — this repository has no `skills/` directory. The project-skill
rules still hold, and the script still enforces them, the moment one is added.

Workspace skills may use these Claude Code extensions, because only this repository's agents load them:

- Frontmatter fields `argument-hint`, `disable-model-invocation`, `user-invocable`, and `model`
- Dynamic context: a `!` followed by a backticked command, which Claude Code runs before loading the skill (see
  §5 for one). Follow each with a line telling the agent to run the command itself if it arrives as literal text
- Comma-separated `allowed-tools`
- Relative links to repository files outside the skill, such as `../../../docs/code/logging.md`

Project skills may use none of them. For how a project skill reaches repository files, see §4.

Commit scopes differ by kind too: `chore(skills)` for workspace skills, `feat(skills)` for project skills. See
`/commit`.

## 2. Frontmatter

`SKILL.md` opens with YAML frontmatter between `---` lines. It must parse as YAML: a value containing `: `
must be quoted, and a value containing `"` is quoted with `'`.

| Field | Required | Rule |
|---|---|---|
| `name` | Yes | 1-64 characters: lowercase `a-z`, `0-9`, and hyphens. No leading, trailing, or consecutive hyphens. Must equal the directory name |
| `description` | Yes | 1-1024 characters. What the skill does, then when to use it |
| `license` | No | A license name, or the name of a bundled license file |
| `compatibility` | No | 1-500 characters. Environment requirements: products, system packages, network access. Omit it when there are none |
| `metadata` | No | A map from string keys to string values. Quote numbers (`version: "1.0"`) and join lists with spaces |
| `allowed-tools` | No | A string of pre-approved tools. Experimental: support varies between agents. Space-separated in project skills |

No other field is allowed in a project skill. Add a field to a workspace skill only when it is in the list in §1;
a new extension is added to that list and to `WORKSPACE_EXTENSION_FIELDS` in `scripts/check_skill.py` in the
same change.

**The `description` is the only part of the skill an agent reads before deciding to load it**, so it carries
the whole discovery burden:

- Name the task in the words a user would say. "Helps with documents" matches nothing; "check a rule document's
  frontmatter, section outline, and length budget" matches the request.
- Say when to use it: the triggers, the error messages, the moment in a workflow.
- Say what it is not for, when a sibling skill covers the neighboring task.

## 3. Body

The body has no required format. Write what helps an agent do the task: steps, examples of input and output,
edge cases.

**Budget for progressive disclosure.** An agent loads `name` and `description` for every skill at startup,
the whole `SKILL.md` body on activation, and other files only when the body sends it to them. So:

- Keep `SKILL.md` under 500 lines, and under about 5000 tokens.
- Move a workflow that most activations do not need into `references/<topic>.md`, and say in `SKILL.md` when
  to read it.
- Keep each reference file on one topic. An agent reads the whole file.

| Directory | Holds |
|---|---|
| `scripts/` | Executable code the agent runs. Self-contained or with dependencies declared inline (`uv run --script`), with useful error messages |
| `references/` | Documentation the agent reads on demand |
| `assets/` | Static resources: templates, schemas, data files |

## 4. Links

Link relative to the file holding the link, never with a leading `/`. From `SKILL.md` that means relative to
the skill root: `references/workflow-raw.md`.

**Keep references one level deep.** `SKILL.md` links to a reference file; a reference file should not send
the agent on to a third file for something it needs to finish the task.

A project skill cannot link outside its directory: once installed elsewhere, the target is not there. To
depend on a repository file, list it in `metadata` under the subkey naming the skill directory it is linked
from, and link it as `<subkey>/<file name>`:

```yaml
metadata:
  references: docs/code/logging.md docs/code/python-typing.md
  assets: docs/__meta__/code.md
```

```markdown
See [logging](references/logging.md) and [the corpus specification](assets/code.md).
```

The subkeys are `references`, `assets`, and `scripts`, after the directories in §3. File names must be unique
within a subkey, because the link keeps only the file name.

`metadata` is also the reverse index: `scripts/check_skill.py --linking docs/code/logging.md` names every skill
that depends on that file, which is how a document change finds the skills it may have stranded (§8).

## 5. The changeset

!`git status --short -- .agents/skills skills`

> If the block above is literal text, the runtime did not execute it. Run that command yourself first.

Uncommitted work is the default subject. For a whole branch use
`git diff --name-only $(git merge-base HEAD main)...HEAD -- .agents/skills skills`. Given explicit paths, check
those instead. A change to any file in a skill directory is a change to that skill.

A change under `docs/` is also a change to every project skill that links the file. Add those skills to the
subject: `scripts/check_skill.py --linking <path>` (one `--linking` per file) prints them, one per line.

## 6. Run the script

**`scripts/check_skill.py`** decides every mechanical rule: frontmatter fields and limits, `name` against the
directory, YAML validity, the 500-line budget, `metadata` value types, `metadata` linked files existing and
unique, every relative link resolving including its `#fragment`, links escaping a project skill, and Claude
Code syntax in a project skill. Do not check those by hand.

It is executable and declares its own dependencies, so run it directly; `uv` resolves them on the first run.
It finds the repository root by walking up, so the working directory does not matter:

```bash
.agents/skills/skills-check/scripts/check_skill.py                        # every skill
.agents/skills/skills-check/scripts/check_skill.py .agents/skills/code-test   # named skills
.agents/skills/skills-check/scripts/check_skill.py --linking docs/code/logging.md   # skills that link a file
.agents/skills/skills-check/scripts/check_skill.py --format json          # machine-readable
.agents/skills/skills-check/scripts/check_skill.py --help                 # flags and exit codes
```

Findings print to stdout as `path:line: [rule] message`; the skill count goes to stderr. Exit 0 means no
findings, 1 means findings, 2 means bad usage.

Name skill directories, not the directory that holds them: a bare `.agents/skills/` is read as one skill and
reports `skill.location`. Pass no paths to check them all — that is what `just check-skills`, the repository's
gate, runs.

## 7. Walk what the script cannot decide

For each changed skill, check:

- [ ] The `description` names the task in the user's words and says when to use the skill
- [ ] `compatibility` is present only when the skill has real environment requirements, and names them
- [ ] Content most activations do not need is in `references/`, and `SKILL.md` says when to read each file
- [ ] No reference file sends the agent to another file for something it needs to finish the task
- [ ] Every `scripts/` file is executable, declares its dependencies, and fails with a useful message
- [ ] A project skill assumes nothing about this repository: no workspace skill names, no `just` recipes, no
      paths outside what `metadata` links in
- [ ] Every command in the body is covered by `allowed-tools` if the skill pre-approves any, and no pattern
      there is broader than the commands need
- [ ] A recipe or command the skill names exists — `just --list` and `--help` are the authorities, not memory

## 8. Behavior the skill restates

A skill may restate a default, a limit, a rule id, or a section outline from a document under `docs/` so an
agent does not need to open the document. Each restatement is a copy that the document's next change strands,
and no script can tell a stale copy from a fresh one. So:

- For a changed project skill, list what it restates from each file in `metadata.references`, and check each
  item against the document's current text. A link to the document's section beats a copied value where the
  agent can afford the read.
- For a changed document, take the skills that `--linking` named (§5) and do the same for the sections that
  changed. A skill that restates something the document no longer says is a finding against the skill, in the
  same change.
- When the document and the code disagree, that is `/feat-validate`'s finding, not this skill's. Report it
  there and keep the skill on the document's side until it is settled.

## 9. Report

Clean:

> Skills check clean. Checked: `.agents/skills/code-test`, `.agents/skills/skills-check`.

Violations, per skill, most severe first, one per line, with the fix:

> `.agents/skills/code-test/SKILL.md:3` — **description**: says what the skill does but not when to use it.
> Add the triggers, such as "after editing a file under `src/`" or "a test failed".
>
> `.agents/skills/code-test/SKILL.md:41` — **restates**: says the unit tier is selected with `-k unit`;
> `pyproject.toml` marks it `-m unit`. Update the value or link the section.

Every finding cites the specification's rule or a rule in this skill. A finding with neither behind it is a
style opinion: drop it.

## Pre-approved Commands

These run without user permission:

- `.agents/skills/skills-check/scripts/check_skill.py` with any flags, and `just check-skills`: read-only, no
  side effects
- `git diff`, `git status`, and `git merge-base`
- `ls` on any directory under `.agents/skills/` or `skills/`
- Reading any file under `.agents/skills/`, `skills/`, or `docs/`

## Not This Skill

| Use | For |
|---|---|
| `/docs-rules-check` | checking a document under `docs/` against its specification |
| `/feat-validate` | whether the feature doc a skill restates matches the implementation |
| `/code-rules-check` | checking code against the rule documents in `docs/code/` |
| `/commit` | the commit scope for a skill change |
