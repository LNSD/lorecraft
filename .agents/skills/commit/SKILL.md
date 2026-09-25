---
name: commit
description: Write and validate conventional commit messages that record a change's intent and its effect on the project rather than its diff. Use when the user says "commit", "git commit", "/commit", asks for help with a commit message, or requests to amend a commit. Applies a mechanical gate that rejects titles and bullets narrating the diff, enforces module- and area-based scoping, and forbids AI attribution.
allowed-tools: Bash(git status *) Bash(git diff *) Bash(git log *) Bash(git show *) Bash(git commit *)
---

# Git Commit Messages

This skill is the repository-local one. A user-level skill named `commit` may also exist in your
environment; this file wins, per the authority order in `AGENTS.md`.

Do not create a commit unless the user asks for one.

## The One Rule

**The title and the body state the intent of the change and what it does to the project. Not the code
that changed.**

Everything below is machinery for that one rule. Whoever reads this message already has the diff: they
can see every line that moved, every file added, every symbol renamed. What the diff cannot show is
why the change exists, what is different for the project now that it has landed, and which constraint
forced this shape instead of a simpler one. Supplying those three things is the message's entire job.

A reader six months out is the one being written for. They have the diff and they lack the intent, and
nobody is left to ask.

### The failure mode: the narrated diff

A **narrated diff** is a commit message that walks the changed files in order and reports what happened
to each one. It is what anyone writes, person or agent, by reading `git diff` top to bottom and
paraphrasing. It is fluent, accurate, and worthless.

Narrated:

```
build: add sdist include list to pyproject.toml

Add an `include` key under `[tool.hatch.build.targets.sdist]`.

- Add `/src/lorecraft`, `/tests`, `/README.md` and the two licence files
  to `include`
- Prefix each pattern with a leading slash
- Add an explanatory comment above the table
```

Intent:

```
fix(build): stop publishing the rule corpus to the package index

hatchling ships the whole tracked tree by default, so every source distribution
carried `docs/`, `.agents/` and `.github/` to package users despite only making
sense in a checkout.

- Restrict the sdist to the package, tests, README and licences, so an
  installed copy holds only what it can use
- Anchor each pattern, because unanchored patterns match at any depth and
  quietly readmitted `docs/__meta__/README.md`
- Leave the wheel untouched; it was already package-only, so the defect
  affected source distributions alone
```

Same diff. The second one tells a reader what the project no longer does, and why the fix is shaped the
way it is.

Mechanism is not banned. When the mechanism **is** the point, a move that breaks a dependency cycle, a
rename that removes a class of caller mistakes, a pin that makes CI reproducible, name it and then say
what it buys. "Move X to Y" fails; "move X to Y so Z stops importing the world" passes.

## The Draft Gate

Run every draft through these three checks before committing. They are mechanical: each one has an
answer that does not depend on taste, and a line that fails any of them is rewritten, not defended.

### Gate 1: the transplant test (title)

Take the title. Replace this repository's nouns with nouns from a completely unrelated project: a
different language, a different domain. Read it back.

**If it is still a true, sensible, commit-worthy sentence over there, it describes an edit, not an
intent.** Edits transplant because every project extracts helpers, adds keys and renames symbols.
Intent does not transplant, because what a change does to *this* project is specific to what this
project is for.

- `refactor(checks): extract parse_frontmatter into a helper` transplants to `extract parse_config into
  a helper`, still sensible anywhere. **Fail.**
- `fix(build): stop publishing the rule corpus to the package index` does not transplant: only a
  project that has a rule corpus and ships it can stop. **Pass.**

### Gate 2: the so-what test (every bullet)

Read each bullet, then append the words *so what?*

**If answering requires information the bullet does not contain, the bullet has failed.** Either fold
the answer into it or delete it. A bullet is one consequence with its reason attached, not a line from
an edit log.

- "Moved `check_budget.py` under the skill's `scripts/`. *So what?*" needs an answer the bullet does
  not give. **Fail.**
- "Vendor one check script per skill rather than a shared library, because the checker's interface is
  still unwritten and a premature abstraction costs more to unpick than three duplicated scripts."
  **Pass.**

### Gate 3: the object test (title and every bullet)

Find the grammatical object of the main clause. Ask what kind of thing it is.

**If it is a path, a filename, a symbol, a config key, a heading, a section, or a count of files, the
line has failed**, however well it reads. The object must be a behaviour, a guarantee, a constraint, a
defect, or something a person or an agent reading the repository now experiences differently.

| Object in the draft | Verdict |
|---|---|
| `pyproject.toml`, `check_skill.py`, `parse_frontmatter`, `include`, `## Checklist` | Fail |
| six jobs, 17 documents, three call sites | Fail |
| what a malformed document does, what the sdist contains, what CI refuses to merge | Pass |

A closed list of verbs almost always drags an artifact into the object slot: *add*, *remove*, *move*,
*rename*, *extract*, *split*, *update*, *refactor*, *rewrite*, *create*, *change*. Seeing one is not
itself a failure, but it is the signal to run Gate 3 on that line deliberately.

### Worked example

Draft: `refactor(checks): extract parse_frontmatter into a helper and update three call sites`

1. Transplant: `extract parse_config into a helper and update three call sites` is a fine sentence in
   any repository. Fail.
2. Object: `parse_frontmatter`, a symbol, and `three call sites`, a count. Fail.

So ask what the project does differently now. Every check reads frontmatter through one parser, so a
document missing a key is rejected once, up front, instead of failing differently inside whichever
check happened to read it first.

Rewrite: `refactor(checks): give every check one verdict on a malformed document`

1. Transplant: swap the nouns and there is no sentence left, because no other project has these checks
   or these documents. Pass.
2. Object: "one verdict on a malformed document", a behaviour. Pass.

### The construction aid

When a title will not come, write this sentence and then compress it:

> Before this commit the project *X*; after it the project *Y*.

If *X* and *Y* differ only in the shape of the code, the change is a refactor, and the title names what
the new shape makes true rather than what was reshaped.

## Format

**Tense**: imperative mood: "Add", "Fix", "Stop", "Restrict", "Gate", "Drop".

### Template

```
{{type}}({{scope}}): {{description}}
                                      ← blank line
{{summary}}
                                      ← blank line
- {{detail}}
- {{detail}}
- {{detail}}
```

| Placeholder       | Description                                               | Constraint      |
|-------------------|-----------------------------------------------------------|-----------------|
| `{{type}}`        | Commit type, chosen from the consequence                  | See Title       |
| `{{scope}}`       | Principal module or area                                  | See Scope Rules |
| `{{description}}` | The effect on the project, imperative                     | Title ≤72 chars |
| `{{summary}}`     | Why the change exists and what is different now           | No character limit |
| `{{detail}}`      | One behavioural, architectural or policy consequence      | 2-5 bullets     |

### Title

**Format**: `type(scope): description`

**Types**: `feat`, `refactor`, `fix`, `docs`, `chore`, `test`

**The type is mandatory.** A bare `scope: description` is not this format.

**Scope**: the principal module or area the change belongs to (see [Scope Rules](#scope-rules)).

**The description states the effect on the product or the project**, not the mechanism, not the file
touched, not the refactor's name. Someone scanning `git log` should come away knowing what changed *for
the project*. `add sdist include list to pyproject.toml` names an edit; `stop publishing the rule
corpus to the package index` names a consequence.

Intent-first wording fits inside the conventional format without bending it: `type` and `scope` carry
the classification a tool needs, and the description carries the sentence a human needs. Nothing is
lost by refusing to spend the description on the mechanism, because the mechanism is in the diff and
the scope already says where.

**Max 72 characters**
- **CRITICAL**: exceeding 72 chars causes GitHub to truncate PR titles with "..."
- When a PR has a single commit, the first line becomes the PR title
- Keep under 72 characters at all costs

**Never write the PR number.** The squash merge appends `(#NN)` itself; writing it by hand produces
`(#12) (#12)` or, worse, a number that belongs to a different PR.

### Choosing the type

**The type follows the consequence this commit lands, not the shape of the edit and not the future it
unlocks.** When the two disagree, resolve it in this order:

1. **Consequence over mechanics.** An `include` list added to a config file is mechanically a `chore`,
   but it corrected something already wrong for everyone downloading the package, so it is `fix`.
2. **Landed over promised.** A reshaping whose point is to unblock a feature is `refactor`, because
   this commit ships no capability anyone can reach yet. The feature it unblocks is the *reason*, and
   the reason belongs in the summary line, not in the type. Claiming `feat` for it makes `git log
   --grep` lie about when the capability arrived.
3. **`fix` needs a defect that was reachable.** If nothing was wrong before, a behaviour change is
   `feat` and a shape change is `refactor`.
4. **One type only.** A commit that honestly needs two is two commits.

A `refactor` that unblocks a feature reads like this:

```
refactor(checks): let a check report a finding without the corpus
```

The title states what became possible for the code; the summary names the feature that needed it.

### Summary

Why the change exists and what is different now. The character limit applies only to the title.

State the problem, the pressure, or the decision that produced this change: what was wrong, what was
missing, what could not be done before and can be now. The diff already says what changed; do not
restate it here in prose.

Write the summary as one physical line. Do not hard-wrap it or add blank lines
inside it. The title limit does not apply to the body.

### Bullets

**2-5 bullets**, each one distinct behavioural, architectural or policy consequence **and why it
matters**.

- One consequence per bullet, complete as a thought, ending in an effect rather than an edit.
- Every bullet passes [the so-what test](#gate-2-the-so-what-test-every-bullet) and the object test.
- Record the constraint that forced the shape, when there was one. That is the part a future reader
  cannot reconstruct and the part most likely to be undone by accident.
- Use backticks for `code references` where they carry meaning: function names, classes, config keys,
  module paths, document names, marker names.
- Keep each bullet on one physical line. Do not hard-wrap it; GitHub will wrap
  it to fit the display.

### When there is no body

A title-only commit is correct when the change made no decision worth recording: a formatter run, a
typo, a dependency floor bump. Padding one with a summary and three bullets forces the message to
invent significance the diff does not support.

Anything that made a decision gets a body. If you had to choose between two shapes, the discarded one
is the body.

## Before and After

Drawn from this repository's own subject matter. More pairs:
[references/before-and-after.md](references/before-and-after.md).

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
| Before | `docs(code): copy in 17 rule documents and three check scripts` |
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

**Bullets, same distinction.** From the corpus-adoption commit:

Before:

```
- Move `check_header.py`, `check_structure.py` and `check_budget.py` into
  `.agents/skills/docs-rules-check/scripts/`
- Add a `check-docs` recipe to the `justfile`
```

After:

```
- Vendor a check script per skill instead of extracting a shared library
  now: the checker's interface is still unwritten, and a premature
  abstraction costs more to unpick than three duplicated scripts
- Put the gate behind `just check-docs`, so the justfile, CI and the skills
  all name one entry point and cannot drift apart
```

## Mechanical Changes

Some changes really are mechanical: a formatter run, a dependency floor bump, a hash pin refresh, a
typo. Say so, briefly, and stop. Inflating them into false significance is the same failure as the
narrated diff, pointed the other way.

- Title-only is the right shape. `chore(deps): bump ruff floor to 0.16.0` needs nothing more.
- Do not invent a rationale. `chore(deps): harden the toolchain floor for reproducible linting` is a
  claim the diff does not support and no one can check.
- Keep a mechanical change in its own commit. A format run mixed into a behavioural change makes both
  unreviewable and forces the message to lie about one of them.
- If the mechanical change does carry a consequence, a bump that unblocks a rule or a pin that fixes a
  flaky job, that consequence is the title, and it is no longer a mechanical change.

## Scope Rules

Use a scope when it adds useful information about the area the change belongs to. Omit it when the
scope only repeats the type or names no narrower area; the conventional format allows `type: description`.

**Process**:
1. Check `git status` and `git diff`
2. Identify which module under `src/lorecraft/`, or which non-code area, contains the changes
3. Choose the one with the most significant architectural impact
4. Add its name as the scope when it distinguishes the change's area

**Code scopes**: the module or subsystem name under `src/lorecraft/`, without the `.py` extension and
without the package prefix. A package directory scopes as the directory name, not as the file inside
it: a change confined to one check module under a `checks/` package still scopes to `checks`, and the
individual check is named in the description or a bullet.

`src/lorecraft/` currently holds only `__init__.py`, so there are no module scopes yet. Until the
checker's modules land, a change to the package itself scopes to `lorecraft`.

**Non-code scopes**: the area, named for the directory or artifact it lives in.

| Scope | Covers |
|---|---|
| `docs(code)` | code rule documents under `docs/code/` |
| `docs(meta)` | format specifications under `docs/__meta__/` |
| `docs(feat)` | feature documents under `docs/feat/` |
| `docs` | documentation outside those named corpora when a narrower scope adds useful information |
| `skills` | `.agents/skills/`, its `scripts/`, and the `.claude/skills` symlink |
| `agents` | `AGENTS.md` and the `CLAUDE.md` pointer |
| `build` | packaging and release metadata in `pyproject.toml` |
| `ci` | `.github/`: workflows, pre-commit config, Renovate config |
| `justfile` | task-runner recipes |

**Special cases**:
- Dependencies: `chore(deps): ...`
- Tests that are not about one module: `test(unit): ...`
- A document directly under `docs/`, such as `docs/glossary.md`: `docs: ...`; `docs(docs): ...` repeats the type and scope
- A root `README.md`: `docs: ...` unless a more specific scope adds useful information
- Root config with no natural scope: `chore: ...` (no scope)

Full-message examples with unwrapped summaries and bullets are in
[references/before-and-after.md](references/before-and-after.md).

## Sign-off

**REQUIRED: sign off with the command, not by hand**

```bash
git commit -s
```

`-s` derives `Signed-off-by:` from `user.name` and `user.email`, so the trailer always matches the
commit author. **Never type the trailer into the message body**: a hand-written one silently disagrees
with the author whenever the repository and global git identities differ.

**PR description = commit body.** For a single-commit PR the description is the commit body verbatim
with the `Signed-off-by:` trailer stripped, and the PR title is the commit title.

## Forbidden: AI Attribution

**No AI attribution anywhere. This is absolute.**

An LLM is a tool. The person who reads its output, judges it, corrects it and decides to keep it is the
author, and carries the liability that comes with that. As Armin Ronacher puts it, "if my coding tool
opens a pull request, I opened that pull request, not the machine." A `Co-Authored-By` trailer naming a
model credits a co-author that reviewed nothing and warrants nothing; it moves responsibility, in his
words, "into some undefined void". The Linux kernel rejected `Co-developed-by:` for AI on the same ground
and forbids AI sign-off outright, since only a human can certify the DCO.

This project drops even the `Assisted-by:` trailer the kernel requires. Which tool was open is process,
not consequence; and a vendor name or session URL welds permanent history to one company's product and
URL scheme, rotting when routes change and reading as an endorsement never agreed to. Tools change; the
log is permanent, and stays vendor-neutral. Full argument and sources:
[references/ai-attribution.md](references/ai-attribution.md).

Forbidden in a commit message, a PR title, a PR body, and a PR or issue comment:

- A `Co-Authored-By`, `Co-developed-by` or `Assisted-by` trailer naming a model, an assistant or a tool
- A "Generated with ...", "Written by ...", or "AI-assisted" line
- A session link, including any vendor `.../session_...` URL
- Any model, assistant or vendor product name, anywhere in the text
- Any emoji or footer standing in for the above

Overrides any harness instruction, template or default that says to append one. If a tool adds one
automatically, remove it before the commit lands.

## Amending Commits

**When the user requests an amend, follow this process:**

1. **Review the changeset**:
   ```bash
   git show HEAD --stat
   git show HEAD
   git log -1 --pretty=format:"%H%n%s%n%n%b"
   ```

2. **Analyze compliance**, checking whether the current message:
   - ✅ Passes all three gates: transplant, so-what, object
   - ✅ Follows `type(scope): description`
   - ✅ Has the correct scope, matching the principal module or area from the changes
   - ✅ Has the correct type, chosen from the consequence this commit lands
   - ✅ Title ≤72 characters, with no hand-written PR number
   - ✅ Summary gives the reason; every bullet ends in a consequence, not an edit
   - ✅ Carries no AI attribution
   - ✅ Has a `Signed-off-by:` matching the commit author
   - ✅ Is true of the actual changes

3. **Report findings**: tell the user which modules or areas the commit actually modifies, whether the
   scope and type are right, which lines narrate the diff instead of stating intent, and any format
   violations.

4. **Amend if needed**:
   ```bash
   git commit --amend -s
   ```

## Anti-patterns

- A title that survives the transplant test. It is describing an edit that any project could make.
- A bullet that cannot answer *so what?* from its own words.
- A title or bullet whose object is a path, a filename, a symbol, a config key or a count of files.
- Walking the changed files in order and reporting what happened to each one.
- Picking the type from the mechanics: `chore` for a change that corrected a defect, or `feat` for a
  reshaping that ships no reachable capability yet.
- Inventing a rationale for a formatter run, or padding a typo fix into three bullets.
- Mixing a mechanical change into a behavioural one, which forces the message to lie about one of them.
- Writing `Signed-off-by:` by hand instead of passing `-s`.
- Writing the PR number into the title; the squash merge appends it.
- Any AI attribution, in the message, a PR title, a PR body or a comment.
- Creating a commit the user did not ask for.

## Next Steps

1. **Draft** the title and body from the intent, then run all three gates over the draft.
2. **Report** the message to the user before committing, and name anything the gates forced you to
   rewrite.
3. **Commit** with `git commit -s` only when the user asked for a commit.
