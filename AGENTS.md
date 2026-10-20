# Lorecraft - Agent Guide

Lorecraft is a toolkit for the agent-facing documentation of a repository: its coding-rule documents, its
feature docs (specs, plans, status), the agent skills it carries, and the format specifications that govern
all three. It implements the mechanical half of reviewing those documents — frontmatter against a schema,
section outlines against a structure spec, prose against a length budget, skills against the Agent Skills
specification — so a repository declares the rules it wants and runs one checker, instead of carrying a
standalone script per check. It is one Python package, `lorecraft`, managed with `uv`, and a private package
beside it, `lorecraft-gen`, that holds the code writing the generated files:

- `src/lorecraft/` is the package, in the layers the import-linter contract in `pyproject.toml` names and
  enforces; read it rather than assuming a set.
- `gen/` is `lorecraft-gen`, import package `lorecraft_gen`: one module per generator, run by a `gen-*` recipe that installs it
  on the fly with `uv run --with-editable ./gen` and passes it its output directory as `--outdir`. It is not in the
  root project's workspace, environment or lock.
  It imports `lorecraft`, nothing in `lorecraft` imports it, and it is never built or published. It carries no
  tests: `just gen` leaving the tree clean, which CI's `gen-check` enforces, is the check on a generator.
  `docs/code/package-lorecraft.md` and `docs/code/package-lorecraft-gen.md` state what each package is, publishes and
  may import.
- `tests/` holds the integration and end-to-end tiers and the end-to-end helper library. None of it is built.

This guide holds workflow and policy, and points to where everything else is documented:

- **What the toolkit ships** — its commands, the checks they run, the specification dialects — is in
  `docs/feat/`, one feature per document. Find one through `/feat-discovery`.
- **How the code is built** is in `docs/arch/` and `docs/code/`: the accepted ADRs in `docs/arch/` state the
  architecture every package fits into, and each layer's `module-*` document in `docs/code/` states its single
  responsibility and what stays out of it, and the `package-*` documents state which packages are published,
  which are private, and which may import which. Load what a task needs through `/code-rules`.
- **How a document under `docs/` is written** is in `docs/__meta__/`: `README.md` explains how a document's path
  selects the specifications that govern it, and each specification states its corpus's rules. Write through
  `/docs-rules`, check through `/docs-rules-check`.

Do not infer structure that is not on disk.

## Quick Start

If you are an AI agent working on this repository, follow these rules first:

1. Read this file, then look at what exists on disk. The toolchain, the document format and the checks are
   fixed; the feature docs under `docs/feat/` say what the library ships.
2. Ask a concise question when a task needs a convention this guide does not fix. Decisions this repository
   has not made — where a check lands in the library, a new feature doc — belong to the owner.
3. Run everything Python through `uv run`. Never install into a system interpreter, never use bare `pip`.
4. Keep changes small and readable. Readability over cleverness, always.
5. Update this guide in the same change that makes one of its statements untrue.
6. Never open a pull request on your own. A person who answers for the change opens it, and a pull request
   opened by an autonomous agent is closed without review, as `CONTRIBUTING.md` states.

## Authority Order

When guidance conflicts, use this precedence:

1. A direct instruction from the user in the current session.
2. Skills in `.agents/skills/` and `skills/` — command workflows, selection rules, and operational details.
3. `AGENTS.md` — repository-level workflow, policy, and navigation.
4. Rule and format documents under `docs/` — `docs/__meta__/` governs the form of a document, `docs/code/`
   governs the code.
5. Tool defaults and general practice.

Do not duplicate command recipes in project docs: command behaviour lives in the relevant skill.

## Dogfooding

**Every check this repository ships is pointed at this repository.** A check lands as three things at once: the
check in the library, a `just` recipe that runs it over this repo's own `docs/`, `.agents/skills/` and `skills/`,
and a CI job running that recipe. **A check that cannot pass this repository does not ship.** When a check reports
a finding, fix the document or fix the check — never loosen a schema, raise a cap or budget, or narrow a recipe's
scope to make it green.

A check lives in the library, and a skill that runs one calls the `lorecraft` command rather than carrying the
code. The standalone scripts left are `.agents/skills/feat-status/report.py`, at its skill's root, which the library
is to replace, and the git workflow scripts under `.agents/skills/code-*/scripts/`, plain standard-library
`python3` that drives `git`, `just` and `gh` and does no check of its own.

## Canonical Resources

| Resource | Purpose |
|---|---|
| `AGENTS.md` | Project-level agent policy and workflow; this file |
| `CONTRIBUTING.md` | What a pull request needs before it is reviewed, and who may open one |
| `.agents/skills/` | Workspace skills, for agents working on this repository, and a symlink to each project skill |
| `.claude/skills/` | Compatibility symlink to `.agents/skills/` |
| `skills/` | Project skills, shipped for agents in repositories that use Lorecraft |
| `pyproject.toml` | The package's metadata and build, the dev group, the import-linter contracts, and `ruff`, `ty`, `pytest`, `coverage` and `mutmut` config; `ruff`, `ty` and the contracts cover `gen/` too |
| `justfile` | Task runner recipes; wraps `uv` |
| `docs/code/` | Code rules for this repository: `module-*` per layer of `lorecraft`, `package-*` per package |
| `docs/__meta__/` | Specs: a prose `.md` plus its JSON halves |
| `docs/feat/` | Feature docs for this repository |
| `docs/arch/` | Architecture documents written before and while a feature is built: requirements and decision records, numbered in one shared sequence; an accepted ADR binds code like a code rule |
| `docs/schemas/` | JSON Schemas of the specification files' shapes, generated by `just gen`; never edited by hand |
| `docs/rulebook/` | One page per rule code, generated by `just gen` from the rules' docstrings; never edited by hand, fix the docstring |
| `src/lorecraft/rules/index.py` | The identity of every rule as strings and tuples, with its lookups; generated by `just gen`, through `lorecraft_gen`, from the registry and held to it by `gen-check`; never edited by hand, fix the rule's declaration |
| `.github/` | `workflows/ci.yml`, `workflows/release.yml` (publishes a GitHub release to PyPI), the pre-commit config, and `renovate.json5` |
| `src/lorecraft/` | The package, the one thing released |
| `gen/src/lorecraft_gen/` | The generators of the committed generated files, a private package that is never released and has no tests: `just gen` leaving the tree clean is its check |
| `src/**/tests/` | The unit tier: a `tests/` subpackage beside the module it tests, never shipped |
| `tests/it/` | The integration tier, flat, and `rule_cases/`, the fixtures every rule code's trigger and near-miss test runs over |
| `tests/e2e/`, `tests/lib/` | The end-to-end tier, driving the installed console script in a subprocess, and its helpers |

## Skill Routing

Skills live in two places, and the difference is who loads them:

- **`skills/` holds project skills**, shipped to other repositories: the workflow a Lorecraft user follows to
  write and check their specifications, documents, code rules and skills. A project skill assumes nothing about
  this repository — no `just` recipe, no workspace skill, no repository path — and calls the installed
  `lorecraft` command rather than vendoring a script.
- **`.agents/skills/` holds workspace skills**, for working on this repository. It also links each project
  skill in by symlink, named as the skill, so this repository's agents run the same skills its users do: that
  is the dogfooding above, applied to skills. `.claude/skills` is a symlink to `.agents/skills/`, so Claude Code
  and Codex-style agents read the same definitions.

`/skills-check` holds every skill to the Agent Skills specification. This repository adds, by kind:

- A workspace skill may use one extension the specification does not define, because only this repository's
  agents load it. One is dynamic context in the body, a `!` followed by a backticked command that the agent runs
  before loading the skill, each followed by a line telling the agent to run the command itself if it arrives as
  literal text. It does not add a frontmatter field: every skill's frontmatter holds to the six fields the
  specification defines. A project skill uses neither.
- A workspace skill names a repository file as a path in backticks. A project skill links a document of this
  repository by its published URL instead, as `/skills-check` describes.
- `just check-docs` is the gate. It checks every skill an agent reads, so each project skill is checked once,
  through its symlink.
- When a skill restates a feature doc and the doc disagrees with the code, that is `/feat-validate`'s finding.

Commit scopes by kind are `/commit`'s. Prefer a skill over a direct `uv run` or `just` invocation for any
operation it covers. A user-level skill of the same name may exist; the repository-local skill wins.

| Skill | Route to it when |
|---|---|
| `code-rules` | Loading the rule documents from `docs/code/` that apply to the work at hand, frontmatter first |
| `code-rules-check` | Checking a changeset against `docs/code/` — compliance only, not a review |
| `code-review` | Reviewing the working branch: rule compliance, bugs, regressions, security, soundness |
| `code-format` | Formatting Python with `ruff format`, through `just fmt` |
| `code-check` | Linting Python with `ruff check`, through `just check`, auto-fixing the mechanical findings first |
| `code-gen` | Regenerating the committed generated files, such as `docs/schemas/` and `docs/rulebook/`, through `just gen` |
| `code-test` | Running the pytest tiers through `just test-unit`, `just test-it`, `just test-e2e` and `just test`, coverage when asked what the tests reach, and mutation testing when asked how effective they are |
| `code-integrate` | Applying a Code Writer's patch files to a part branch, running the gates, then squashing it into one signed commit and pushing it |
| `code-restack` | Rebasing a stack of pushed part branches onto a moved base, running the gates on each and pushing with a lease |
| `code-sync` | Bringing open pull requests that are behind `main` up to date with a signed rebase, the gates and a leased push |
| `release` | Tagging a release, building the artifacts from that tag, and verifying what they contain |
| `docs-rules` | Writing or editing anything under `docs/` — picks the corpus and the specification that governs it |
| `docs-rules-check` | The review pass over `docs/`: a document against its specs, through `lorecraft check`, and a specification for loading, prose-JSON agreement and resolution |
| `docs-rules-creator` | Writing or changing a specification in `docs/__meta__/`, for any corpus, or adding a corpus or namespace |
| `skills-check` | Writing or checking a skill — **also the skill-authoring guide**; read before any `SKILL.md` edit |
| `feat-discovery` | Answering what a part of the toolkit is or does, from `docs/feat/` |
| `feat-status` | Reporting the maturity each feature doc declares, and which docs are missing a `status` |
| `feat-validate` | Checking that a feature doc's claims exist in code and are covered by tests |
| `commit` | Writing or amending a commit message |

The three `feat-*` skills read `docs/feat/`, which documents what the toolkit ships, one command or one
specification dialect per document; find a document through `/feat-discovery` rather than a list kept here.

## Commands

`just` is the task runner and it wraps `uv`. `just --list` is the authority on which recipes exist and what
each runs, and the skills in [Skill Routing](#skill-routing) say when to run which; this guide lists neither.
Flags pass straight through (`just check --statistics`); when no recipe covers what you need, run it under
`uv run` rather than a system interpreter.

The `uv` version is pinned once, as `required-version` under `[tool.uv]` in `pyproject.toml`. CI's
`setup-uv` and a local `uv` both read it, so a mismatched `uv` fails with a version error; Renovate bumps it.

Generated files are committed, and CI fails when `just gen` would change them; the `code-gen` skill owns when to
run it and the rules for its output.

## Development Workflow

1. Research first. Read the files a change touches and the reference setups it mirrors before planning.
2. Plan from what exists. If the repository does not yet define a convention the task needs, propose one
   explicitly rather than inventing it silently.
3. Implement the smallest correct change. Prefer clear, typed, obvious code over clever abstractions.
4. Update, in the same change, the documents it makes untrue:
   - **User-facing behaviour** — a new or changed command, option, output or specification dialect — creates or
     updates its feature docs in `docs/feat/`; find them through `/feat-discovery`.
   - **A package's responsibility.** Code is written against its layer's `module-*` code rules and its package's `package-*` code rules in
     `docs/code/`.
     A change that fits them updates nothing there. A deliberate decision that changes what a package is
     responsible for, or contradicts its rules, updates those rules in the same change. That is the less common
     case: code that does not fit its package usually belongs in another one, not in a rewritten rule.
5. Format and lint with `just fmt` then `just check`; fix every finding, never a bare `# noqa`.
6. Run the relevant tests: `just test-unit` always, and the tier the change reaches — `just test-it` for a module seam, `just test-e2e` for packaging or the console script.
7. Run `just check-docs` when the change touches `docs/`, `.agents/skills/` or `skills/`.
8. Close by stating what was skipped and any residual risk.

A plan is grounded in what the repository actually contains, and that holds equally when the user asks for one:
confirm which files exist, name the conventions the change depends on, and ask a concise question where
implementing would otherwise be guesswork. A plan that assumes a module layout, a loader, a skill, or a rule
document this repository does not have is invalid — restate it against the real tree.

## Validation Gates

Run `just sync` first, so `ruff`, `ty` and `pytest` are present in the project environment. CI runs the same
list, and `check-docs` is in the `docs` group rather than `check`, so a group-based selection misses it.

| Gate | Requirement |
|---|---|
| Format | `just fmt` after edits and before linting; `just fmt-check` verifies without writing |
| Lint | `just check`, which also runs the import-layering contract; every finding fixed, none silenced with a bare `# noqa`. `just check-fix` first |
| Types | `just check-types`; clean, with no finding silenced by widening an annotation to `Any` |
| Tests | `just test-unit` after lint is clean, then the tier the change touches — `just test-it`, `just test-e2e` — and `just test` when it earns the whole suite |
| Documents and skills | `just check-docs`; `lorecraft check` reports no error over any document under `docs/` or any skill: the frontmatter, outline, length, link and layout rules |
| Commits | `just check-commit-msg`; every commit on the branch passes `gitlint` with `.github/gitlint`, the mechanical half of the `commit` skill's format. `just install-gitlint` installs it as a `uv` tool. CI checks a pull request's own commits |
| Codegen | `just gen` after changing a generator or what it models; it must leave the tree unchanged in CI |

Do not run tests before lint is clean, do not treat a type error as a lint preference — it is a failed gate —
and do not broaden scope for convenience.

## Coding Principles

- Readability over cleverness: someone who does not know the design must follow the code top to bottom. Prefer
  the obvious construct; shorter but harder to explain is a regression.
- **Type annotations are a requirement, not a preference.** Every signature, dataclass field and module-level
  constant carries one: an unannotated signature is an incomplete contract and a wrong annotation is a defect,
  not a stale comment. `just check-types` must be clean before a change is done, `Any` needs a reason at the spot
  it appears, and [docs/code/python-typing.md](docs/code/python-typing.md) owns the spelling.
- Do not add an abstraction, a generic, or a callback parameter to save a few lines.
- Prefer types that prevent invalid states over defensive checks for states that "shouldn't happen", and
  validate external input at boundaries rather than throughout trusted internal code.
  [docs/code/python-typing.md](docs/code/python-typing.md#1-make-an-invalid-state-unrepresentable) owns making
  an invalid state unrepresentable.
- Never expose secrets, keys, or credentials; use environment variables.
- When something genuinely must be subtle, say why in a comment at that spot.

## Rule Documents

`docs/__meta__/code.md` is the authority for the code rules in `docs/code/`, and the namespace specifications
beside it narrow it for their groups. Read the specifications that govern a document before writing it; the
`/docs-rules` skill finds them.

## Testing

[tests-organization](docs/code/tests-organization.md) owns the tiers and where a test lives,
[tests-functions](docs/code/tests-functions.md) the shape of a test, and the `code-test` skill the recipes,
snapshots included. Run tests through the `just` recipes, never a bare `pytest`; CI runs `just test`.

## Commits

Do not create commits unless the user asks for one. The `commit` skill owns the message format; these rules
cannot be relaxed:

- Conventional Commits format: `type(scope): subject`, signed off with `git commit -s` rather than a
  hand-written trailer; the flag derives it from git config.
- **Never add AI attribution.** No `Co-Authored-By` trailer naming a model or tool, no "generated with" line,
  no session link, and no model or tool name in a commit message, a PR title, a PR body, or a PR comment.
  This binds every message an agent writes here. An `Assisted-by:` trailer a contributor added to their own
  commit, as `CONTRIBUTING.md` allows, is theirs: keep it when amending or squashing that commit.
- Do not write the PR number in a commit message; the squash merge appends it. For a single-commit PR, the
  description is the commit body verbatim with the `Signed-off-by:` trailer stripped, and the title is the
  commit title.

## Essential Conventions

- Keep docs and code in sync in the same change: feature docs for behaviour, `module-*` code rules for a
  package's responsibility ([Development Workflow](#development-workflow), step 4).
- **No file holds a version.** `hatch-vcs` derives it from the git tag at build time, and the command line
  alone reads it back with `importlib.metadata`;
  the `release` skill owns the release flow. Adding a version literal anywhere is a defect, not a
  convenience. The exceptions are a rule's `SINCE` and a removed rule's `REMOVED_IN`, immutable literals
  naming the release that first shipped the rule or removed it, never the current version, and the fixed `0.0.0`
  of the private `lorecraft-gen`, which has no release.
- Do not add a dependency without a stated reason; this is a small toolkit, and the standard library is
  preferred until it is genuinely insufficient.
- Keep this guide honest: a section describing something that does not exist must say so.
