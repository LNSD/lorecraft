---
name: skills-check
description: Write agent skills that comply with the Agent Skills specification, and check the skills a repository's agents read against it with lorecraft check - frontmatter, the 500-line budget, links, and what no check can decide. Use before creating or editing a SKILL.md or any file in a skill directory, when reviewing a skill change, before committing one, or when lorecraft check reports a diagnostic in a skill
compatibility: Requires the lorecraft command, on PATH or run through uvx lorecraft, or uv run lorecraft in a uv project that declares Lorecraft as a dependency, and a git checkout
allowed-tools: Bash(lorecraft check*) Bash(lorecraft inspect*) Bash(uvx lorecraft check*) Bash(uvx lorecraft inspect*) Bash(uv run lorecraft check*) Bash(uv run lorecraft inspect*) Bash(git diff *) Bash(git status *) Bash(git merge-base *) Bash(grep -l *)
---

# Skills Check

Agent skills follow the [Agent Skills specification](https://agentskills.io/specification). This skill is both
paths: **§1-§4 are how to write a skill**, §5-§9 are how to check one. It checks format, discovery, and
structure. It does not check whether the behavior a skill describes is right, and §8 says what to do when a
skill's source disagrees with the code.

The specification is the authority. Where this skill and the specification disagree, the specification wins
and this skill has a bug. A repository may allow more in skills only its own agents load; its agent
instructions say what, and where they say nothing, the specification alone applies.

## Running lorecraft

Every command below calls `lorecraft` directly. Where it is not on `PATH`, run `uvx lorecraft …` instead, or
`uv run lorecraft …` in a uv project that declares Lorecraft as a dependency. Run from the repository root.

## 1. Where agents read skills

An agent reads skills from its skills directories, such as `.agents/skills` or `.claude/skills`. List the ones
the repository has, and every skill with the agents that read it:

```bash
lorecraft inspect                 # the skills follow the corpora in the tree
lorecraft inspect --format json   # agent_skills_dirs and skills
```

[cli-inspect](https://github.com/LNSD/lorecraft/blob/main/docs/feat/cli-inspect.md) describes the output. A skill is
known by the entry an agent lists. A skill kept in a directory no agent reads is linked into a skills directory by a
symlink, and the symlink takes the skill's name, because that entry is the name an agent knows it by. `lorecraft check
skills` reads the skills where agents list them, so it checks a linked skill once, through its entry.

## 2. Frontmatter

`SKILL.md` opens with YAML frontmatter between `---` lines. It must parse as basic YAML, with string keys and no
anchors, aliases or tags: a value containing `: ` must be quoted, and a value containing `"` is quoted with `'`.

| Field | Required | Requirement |
|---|---|---|
| `name` | Yes | 1-64 characters: lowercase `a-z`, `0-9`, and hyphens. No leading, trailing, or consecutive hyphens. Must equal the name of the directory an agent lists the skill by, through any symlink |
| `description` | Yes | 1-1024 characters. What the skill does, then when to use it |
| `license` | No | A license name, or the name of a bundled license file |
| `compatibility` | No | 1-500 characters. Environment requirements: products, system packages, network access. Omit it when there are none |
| `metadata` | No | A map from string keys to string values. Quote numbers (`version: "1.0"`) and join lists with spaces |
| `allowed-tools` | No | A space-separated string of pre-approved tools. `lorecraft check` warns on malformed entries and values over 500 characters, a Lorecraft recommendation rather than an upstream limit. Pattern whitespace stays intact. Experimental: support varies between agents |

No other field is allowed: `lorecraft check` holds every skill to these six and reports anything else as `FM007`
`unknown-field`, including a field one agent reads, such as `model` or `argument-hint`. `FM007` is a warning, so
the run still exits 0: treat a `warning` at a skill path as a finding to fix, not a pass.

**The `description` is the only part of the skill an agent reads before deciding to load it**, so it carries
the whole discovery burden:

- Name the task in the words a user would say. "Helps with documents" matches nothing; "check a code spec's
  frontmatter, section outline, and length budget" matches the request.
- Say when to use it: the triggers, the error messages, the moment in a workflow.
- Say what it is not for, when a sibling skill covers the neighboring task.

## 3. Body

The body has no required format. Write what helps an agent do the task: steps, examples of input and output,
edge cases.

**Budget for progressive disclosure.** An agent loads `name` and `description` for every skill at startup,
the whole `SKILL.md` body on activation, and other files only when the body sends it to them. So:

- Keep `SKILL.md` to 500 lines, frontmatter included, and under about 5000 tokens.
- Move a workflow that most activations do not need into `references/<topic>.md`, and say in `SKILL.md` when
  to read it.
- Keep each reference file on one topic. An agent reads the whole file.

| Directory | Holds |
|---|---|
| `scripts/` | Executable code the agent runs. Self-contained or with dependencies declared inline (`uv run --script`), with useful error messages |
| `references/` | Documentation the agent reads on demand |
| `assets/` | Static resources: templates, schemas, data files |

## 4. Links

Link relative to the skill root, from every file in the skill, never with a leading `/`: the specification
reads a skill's paths from its root. From `SKILL.md` that is `references/workflow-raw.md`; from a file in
`references/`, the entry file is still `SKILL.md`; `../SKILL.md` leaves the skill. A link inside the skill names
a file or a directory the skill holds.

**Keep references one level deep.** `SKILL.md` links to a reference file; a reference file should not send
the agent on to a third file for something it needs to finish the task.

No skill links outside its directory: once installed elsewhere, the target is not there. A file the skill
needs to finish its task belongs in the skill. To point at a document the skill does not carry, link it by its
published URL, which no link rule judges:

```markdown
See [logging](https://github.com/acme/widgets/blob/main/docs/code/logging.md).
```

`metadata` is no way to bring a file in: the Agent Skills specification gives its keys no meaning, so a path
written there is a string like any other, and a link to `references/<file>` it names is broken.

The repository path inside each URL is the reverse index: `grep -l docs/code/logging.md <skills-dir>/*/SKILL.md`,
over each skills directory `lorecraft inspect` lists, names every skill that links that document, which is how a
document change finds the skills it may have stranded (§8).

## 5. The changeset

```bash
git status --short                                         # uncommitted work, the default
git diff --name-only "$(git merge-base HEAD main)"...HEAD  # a whole branch
```

A change to any file in a skill directory is a change to that skill,
whether the directory is an entry an agent lists or the directory a linked entry leads to.

A change to a repository document is also a change to every skill that links it. Add those skills to the
subject: `grep -l <path>` over the skills directories prints them, one per line (§4).

## 6. Run the check

`lorecraft check` decides every mechanical rule. Do not check those rules by hand.

It decides the frontmatter: YAML validity, the six fields and their limits, `metadata` value types, `name`
against the directory an agent lists the skill by, through any symlink, and whether `allowed-tools` entries
follow the list structure above. It also warns when the whole value exceeds Lorecraft's recommendation of
500 characters, including whitespace and patterns. The structure rule splits on whitespace outside parentheses,
so spaces and commas inside a parenthesised pattern stay in that entry, even in an overlong value. It holds `SKILL.md` to 500 lines,
frontmatter included. In every Markdown file of the skill it reports a link that is absolute, that climbs above
the skill root, that names nothing the skill holds, or whose `#fragment` names no heading of its own file. It
reports a symlink an agent would follow out of the repository, wherever it sits in the skill layout.
[check](https://github.com/LNSD/lorecraft/blob/main/docs/feat/cli-check.md#findings) lists the rule groups and their
codes: `FM` for the frontmatter, `LEN002` for the line budget, `LINK` for the links and `LAY001` for a symlink.

```bash
lorecraft check                  # every document and every skill of the workspace
lorecraft check --format json    # machine-readable
lorecraft check --select FM      # one group's rules, by prefix, while fixing them; never the gate
lorecraft check --help           # options and exit codes
```

The run covers the whole workspace, the documents under `docs/` included; read the diagnostics at the paths of the
skills in the changeset. Diagnostics print to stdout as `path:line: severity[CODE]: message`, and may be followed by
`-->`, `= help:` and `= note:` lines, or `labels` and `children` in JSON; the summary goes to stderr. Exit 0 means no
error, warnings included, 1 means at least one error, 2 means the run could not start. A whole run is also the one to
gate on.

## 7. Walk what the check cannot decide

For each changed skill, check:

- [ ] The `description` names the task in the user's words and says when to use the skill
- [ ] `compatibility` is present only when the skill has real environment requirements, and names them
- [ ] Content most activations do not need is in `references/`, and `SKILL.md` says when to read each file
- [ ] No reference file sends the agent to another file for something it needs to finish the task
- [ ] Every `scripts/` file is executable, declares its dependencies, and fails with a useful message
- [ ] A skill installed into other repositories assumes nothing about the one it was written in: no skill,
      task-runner recipe or path that only exists there
- [ ] Every command in the body is covered by `allowed-tools` if the skill pre-approves any, each entry parses as
      a tool name with an optional parenthesised pattern, and no pattern
      there is broader than the commands need
- [ ] A command the skill names exists, with the options it uses — its `--help` is the authority, not memory

## 8. Behavior the skill restates

A skill may restate a default, a limit, a rule id, or a section outline from a repository document so an agent
does not need to open the document. Each restatement is a copy that the document's next change strands, and no
check can tell a stale copy from a fresh one. So:

- For a changed skill, list what it restates from each document it links, and check each item
  against the document's current text. A link to the document's section beats a copied value where the agent
  can afford the read.
- For a changed document, take the skills that `grep -l` named (§5) and do the same for the sections that
  changed. A skill that restates something the document no longer says is a finding against the skill, in the
  same change.
- When the document and the code disagree, that is not this check's finding. Report the disagreement against
  the document, and keep the skill on the document's side until it is settled.

## 9. Report

Clean:

> Skills check clean. Checked: `.agents/skills/review`, `.agents/skills/skills-check`.

Violations, per skill, most severe first, one per line, with the fix:

> `.agents/skills/review/SKILL.md:3` — **description**: says what the skill does but not when to use it.
> Add the triggers, such as "before opening a pull request" or "a change needs scrutiny".
>
> `.agents/skills/review/SKILL.md:41` — **restates**: says the unit tier is selected with `-k unit`;
> `pyproject.toml` marks it `-m unit`. Update the value or link the section.

Every finding cites a requirement of the specification or of this skill. A finding with neither behind it is a
style opinion: drop it.
