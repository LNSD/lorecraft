# Before and after

Referenced from [SKILL.md](SKILL.md) section *Before and After*. Same distinction throughout: the
*before* line names what was edited, the *after* line names what changed for the project and for the
people and agents using it.

## A whole message, from the user's seat

**Naming one skill on the command line checked others too.** The branch closed an issue that showed the
command, its output, and why the output was wrong. The first message was written from the diff anyway:

```
fix(cli): check only the skill entry a path names

A skill is judged as an agent lists it, so the path an argument spells is the skill it names; following the entry's own link selected every entry that shares its directory.

- `select_skills_at` reads an argument as a listed entry first: the links above the entry are followed through the snapshot, the entry keeps its name, and that one skill is selected
- `.agents/skills/beta`, its `SKILL.md`, and `.claude/skills/beta` check `beta` alone, even when it links to another entry
- A path naming the real directory entries link to, such as `skills/gamma`, still selects each entry leading there
- Add `WorkspaceModel.find_skill`, a lexical lookup of a listed skill by its directory
- State the rule in `docs/feat/cli-check-skills.md`, and pin it with integration and end-to-end tests
```

Every sentence is true, and a reader still cannot say what went wrong for whom. The summary is the
mechanism in the abstract; two bullets name internal functions; one lists the documents and tests the
diff already shows. Written from what the issue reported:

```
fix(cli): check only the skill a path names

Naming one skill could check others: with `.agents/skills/beta` a link to `alpha`, `lorecraft check skills .agents/skills/beta` checked `alpha` as well and reported two skills, though only `beta` was asked for. An agent lists `beta` as a skill of its own, so the path names that skill and no other.

- `check skills .agents/skills/beta` checks `beta` alone, named by its `SKILL.md` or through `.claude/skills` alike, so the summary counts the one skill asked for
- `check skills .agents/skills/alpha` no longer drags in every entry linked to it, so a clean skill reports clean
- Naming the directory entries link to, such as `skills/gamma`, still checks each of them, because no agent lists that directory and every skill behind it is the one meant
```

The symptom is reproducible from the summary alone, each bullet is a command and what it now does, and
the one unchanged case says why it stayed.

## Titles

**The source distribution shipped the whole repository.**

| | |
|---|---|
| Before | `build: add sdist include list to pyproject.toml` |
| After | `fix(build): stop publishing the rule corpus to the package index` |

The first names a key added to a config file, which the diff shows in one line. The second names what
the project stopped doing to everyone downstream of a release.

**The rule corpus arrived from an existing setup, deliberately vendored.**

| | |
|---|---|
| Before | `docs(code): copy in 17 rule documents` |
| After | `docs(code): adopt the rule corpus this toolkit exists to check` |

Counting files is the diff's job. The second says the project now holds the corpus the unwritten
checker is being built against, which is why copying rather than abstracting was correct.

**The repository gained CI running its own document and skill checks.**

| | |
|---|---|
| Before | `chore(ci): add ci.yml with six jobs` |
| After | `chore(ci): gate every change on the document and skill checks` |

The first describes a file. The second states the new guarantee: the checks are a gate, not a
suggestion written in prose.

**The version string stopped living in two places.**

| | |
|---|---|
| Before | `refactor(build): move the version out of pyproject.toml into the package` |
| After | `refactor(build): leave the manifest unable to disagree with the package` |

The first is a move. The second is the invalid state the move made unrepresentable, which is the part
worth protecting from a well-meaning future edit.

**A pattern document's structure specification and schema landed under `docs/__meta__/`.**

| | |
|---|---|
| Before | `docs(meta): add code-pattern.structure.json and code-pattern.header.json` |
| After | `docs(meta): make a pattern document fail a check instead of a reviewer` |

The first lists two filenames. The second says what moved out of human review and into a gate, which is
the whole reason a format specification exists.

**A command that validates skills against the Agent Skills specification.**

| | |
|---|---|
| Before | `feat(cli): add a check skills subcommand with frontmatter validation` |
| After | `feat(cli): reject a skill the specification would not load` |

The first describes a subcommand and what it validates. The second names the class of breakage that can
no longer reach `main`.

## Bullets

From the commit that taught `lorecraft check skills` to report a broken link.

Before:

```
- Add `skill.link-broken` to `checks/skill_link.py`
- Call `find_real_path` from the run for each link target
```

After:

```
- Report a link to a file the skill does not hold as `skill.link-broken`, at the line that writes it, so an author fixes the link before an agent follows it to nothing
- Judge a skill's `SKILL.md` and its resources against one view of the repository, so a file changed mid-run cannot pass one and fail the other
```

## Full-message bodies

Keep each summary and bullet on one physical line. Do not hard-wrap the body; there is no body character
limit and GitHub wraps text to fit the display.

```
feat(lorecraft): fail a malformed rule document at the parse boundary

A rule document missing a frontmatter key failed inside whichever check read it first, so the report blamed that check and its author went looking in the wrong place.

- Reject a malformed document before any check runs, so it gets one verdict instead of a different failure per check
- Name the offending key and document together, which tells the author what to fix
- Treat a `name` disagreeing with the filename as malformed, closing the way two documents could claim the same identity
```

```
docs(code): let a typing task load the typing rules alone

The annotation rules lived inside the module-layout document, so an agent that needed them also loaded unrelated layout rules against a fixed context budget.

- Give typing its own document, which `/code-rules` loads on its own
- Leave the module document to layout, imports and `__init__.py` contents, so neither answers questions about the other
- Cross-link both, so arriving at either one still leads to the rule actually wanted
```

```
chore(deps): bump ruff floor to 0.16.0
```
