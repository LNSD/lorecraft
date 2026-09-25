# Lorecraft - Agent Guide

Lorecraft is a toolkit for the agent-facing documentation of a repository: its coding-rule documents, its
feature docs (specs, plans, status), the agent skills it carries, and the format specifications that govern
all three. It implements the mechanical half of reviewing those documents — frontmatter against a schema,
section outlines against a structure spec, prose against a length budget, skills against the Agent Skills
specification — so a repository declares the rules it wants and runs one checker, instead of carrying a
standalone script per check. It is a Python project managed with `uv`.

**The checks are not in the library yet.** They run today as vendored scripts under
`.agents/skills/*/scripts/`, wired to `just check-docs` and `just check-skills` and gated in CI.
`src/lorecraft/` holds the version, the `lorecraft` CLI under `cli/` and nothing else, so the modules those
scripts migrate into do not exist. Do not infer structure that is not on disk.

The CLI is a router: `cli/_app.py` declares the root application and the global options, and every subcommand
lives in its own module under `cli/commands/`, joining by calling `@register(<name>)` beside its handler.
`cli/_registry.py` walks that package and mounts what registered itself, so a new subcommand is a new file —
no dispatcher, no import list, no edit to the root application. `version` is the only one today.

## Quick Start

If you are an AI agent working on this repository, follow these rules first:

1. Read this file, then look at what exists on disk. The toolchain, the document format and the checks are
   fixed; the library and its tests are not written yet.
2. Ask a concise question when a task needs a convention this guide does not fix. Decisions this repository
   has not made — the library's module layout, the first feature doc — belong to the owner.
3. Run everything Python through `uv run`. Never install into a system interpreter, never use bare `pip`.
4. Keep changes small and readable. Readability over cleverness, always.
5. Update this guide in the same change that makes one of its statements untrue.

## Authority Order

When guidance conflicts, use this precedence:

1. A direct instruction from the user in the current session.
2. Skills in `.agents/skills/` — command workflows, selection rules, and operational details.
3. `AGENTS.md` — repository-level workflow, policy, and navigation.
4. Rule and format documents under `docs/` — `docs/__meta__/` governs the form of a document, `docs/code/`
   governs the code.
5. Tool defaults and general practice.

Do not duplicate command recipes in project docs: command behaviour lives in the relevant skill.

## Dogfooding

**Every check this repository ships is pointed at this repository.** A check lands as three things at once: the
script, a `just` recipe that runs it over this repo's own `docs/` and `.agents/skills/`, and a CI job running
that recipe. **A check that cannot pass this repository does not ship.** When a check reports a finding, fix the
document or fix the check — never loosen a schema, raise a budget, or narrow a recipe's scope to make it green.

The scripts under `.agents/skills/*/scripts/` are **vendored copies, deliberately**: a skill stays runnable from
a bare checkout with nothing but `uv`. They are also the migration target — each becomes a module under
`src/lorecraft/`, and the skill then calls the library instead of carrying the code.

## Canonical Resources

| Resource | Purpose | Status |
|---|---|---|
| `AGENTS.md` | Project-level agent policy and workflow | This file |
| `CLAUDE.md` | Single-line pointer to `AGENTS.md` | Exists |
| `.agents/skills/` | Canonical skill definitions, plus the vendored check scripts | 14 skills |
| `.claude/skills/` | Compatibility symlink to `.agents/skills/` | Exists |
| `pyproject.toml` | Package metadata, dependencies, `ruff`, `ty` and `pytest` config | Exists |
| `justfile` | Task runner recipes; wraps `uv` | Exists |
| `docs/code/` | Code rules for this repository | 18 rule documents |
| `docs/__meta__/` | Format specs: a prose `.md` plus its JSON halves | 5 specs, 15 JSON files |
| `docs/feat/` | Feature docs for this repository | Exists and empty, by design — nothing is implemented to document |
| `.github/` | `workflows/ci.yml`, the pre-commit config (off the default root path), and `renovate.json5` | Exists |
| `src/lorecraft/` | The checker package | Exists: `__init__.py`, `_metadata.py`, `__main__.py` and `cli/` |
| `src/lorecraft/cli/` | Root application, command registry and the `commands/` package | 1 subcommand: `version` |
| `tests/` | Three tiers: `unit/` pure logic, `it/` the modules wired together, `e2e/` the installed script | 12 tests, all on the CLI |

## Skill Routing

Skills live in `.agents/skills/`, and `.claude/skills` is a symlink to that directory, so Claude Code and
Codex-style agents read the same definitions. Prefer a skill over a direct `uv run` or `just` invocation for any
operation it covers. A user-level skill of the same name may exist; the repository-local one wins.

| Skill | Route to it when |
|---|---|
| `code-rules` | Loading the rule documents from `docs/code/` that apply to the work at hand, frontmatter first |
| `code-rules-check` | Checking a changeset against `docs/code/` — compliance only, not a review |
| `code-review` | Reviewing the working branch: rule compliance, bugs, regressions, security, soundness |
| `code-format` | Formatting Python with `ruff format`, through `just fmt` |
| `code-check` | Linting Python with `ruff check`, through `just check`, auto-fixing the mechanical findings first |
| `code-test` | Running the pytest tiers through `just test-unit`, `just test-it`, `just test-e2e` and `just test` |
| `code-release` | Tagging a release, building the artifacts from that tag, and verifying what they contain |
| `docs-rules` | Writing or editing anything under `docs/` — picks the corpus and the specification that governs it |
| `docs-rules-check` | Checking a document under `docs/` against its spec; runs the three `check_*.py` |
| `skills-check` | Writing or checking a skill — **also the skill-authoring guide**; read before any `SKILL.md` edit |
| `feat-discovery` | Answering what a part of the toolkit is or does, from `docs/feat/` |
| `feat-status` | Reporting the maturity each feature doc declares, and which docs are missing a `status` |
| `feat-validate` | Checking that a feature doc's claims exist in code and are covered by tests |
| `commit` | Writing or amending a commit message |

The three `feat-*` skills are live but have nothing to read yet: `docs/feat/` is empty, so each reports an
empty corpus rather than an error.

## Commands

`just` is the task runner and it wraps `uv`; `just --list` prints the same set:

| Recipe | What it runs |
|---|---|
| `just sync` | `uv sync --all-groups` — install or refresh the development environment |
| `just fmt` | `ruff format` |
| `just fmt-check` | `ruff format --check`, writing nothing |
| `just check` | `ruff check` |
| `just check-fix` | `ruff check --fix`, applying the mechanical fixes |
| `just typecheck` | `ty check src/lorecraft` |
| `just check-docs` | the three document checks over this repo's own `docs/`; stops at the first that reports |
| `just check-skills` | the skill check over this repository's own `.agents/skills/` |
| `just test-unit` | the unit tier — `pytest -m unit` |
| `just test-it` | the integration tier — `pytest -m it` |
| `just test-e2e` | the end-to-end tier — `pytest -m e2e` |
| `just test` | every tier — `pytest` |
| `just build` | `uv build` — source distribution and wheel |
| `just clean` | remove build, test and cache artifacts |
| `just install-git-hooks` | install the pre-commit hooks; `just remove-git-hooks` undoes it |

Aliases exist for the usual second names: `setup`, `format`, `format-check`, `lint`, `lint-fix`, `check-types`,
`test-all`. Flags pass straight through (`just check --statistics`); when no recipe covers what you need, run
it under `uv run` rather than a system interpreter.

The pre-commit config is not at the default root path, so every `pre-commit` command needs
`--config .github/pre-commit-config.yaml`. `just install-git-hooks` runs exactly
`pre-commit install --config .github/pre-commit-config.yaml --hook-type pre-commit --hook-type pre-push`.

## Development Workflow

1. Research first. Read the files a change touches and the reference setups it mirrors before planning.
2. Plan from what exists. If the repository does not yet define a convention the task needs, propose one
   explicitly rather than inventing it silently.
3. Implement the smallest correct change. Prefer clear, typed, obvious code over clever abstractions.
4. Format and lint with `just fmt` then `just check`; fix every finding, never a bare `# noqa`.
5. Run the relevant tests: `just test-unit` always, and the tier the change reaches — `just test-it` for a module seam, `just test-e2e` for packaging or the console script.
6. Run `just check-docs` and `just check-skills` when the change touches `docs/` or `.agents/skills/`.
7. Close by stating what was skipped and any residual risk.

A plan is grounded in what the repository actually contains, and that holds equally when the user asks for one:
confirm which files exist, name the conventions the change depends on, and ask a concise question where
implementing would otherwise be guesswork. A plan that assumes a module layout, a loader, a skill, or a rule
document this repository does not have is invalid — restate it against the real tree.

## Validation Gates

Run `just sync` first, so `ruff`, `ty` and `pytest` are present in the project environment. CI runs the same
list, and `check-docs` and `check-skills` are in the `docs` group rather than `check`, so a group-based
selection misses them.

| Gate | Requirement |
|---|---|
| Format | `just fmt` after edits and before linting; `just fmt-check` verifies without writing |
| Lint | `just check`; every finding fixed, none silenced with a bare `# noqa`. `just check-fix` first |
| Types | `just typecheck`; clean, with no finding silenced by widening an annotation to `Any` |
| Tests | `just test-unit` after lint is clean, then the tier the change touches — `just test-it`, `just test-e2e` — and `just test` when it earns the whole suite |
| Documents | `just check-docs`; every document under `docs/` passes the header, structure and budget checks |
| Skills | `just check-skills`; every skill passes the Agent Skills specification |

Do not run tests before lint is clean, do not treat a type error as a lint preference — it is a failed gate —
and do not broaden scope for convenience.

## Coding Principles

- Readability over cleverness: someone who does not know the design must follow the code top to bottom. Prefer
  the obvious construct; shorter but harder to explain is a regression.
- **Type annotations are a requirement, not a preference.** Every signature, dataclass field and module-level
  constant carries one: an unannotated signature is an incomplete contract and a wrong annotation is a defect,
  not a stale comment. `just typecheck` must be clean before a change is done, `Any` needs a reason at the spot
  it appears, and [docs/code/python-typing.md](docs/code/python-typing.md) owns the spelling.
- Do not add an abstraction, a generic, or a callback parameter to save a few lines.
- Prefer types that prevent invalid states over defensive checks for states that "shouldn't happen", and
  validate external input at boundaries rather than throughout trusted internal code.
- Never expose secrets, keys, or credentials; use environment variables.
- When something genuinely must be subtle, say why in a comment at that spot.

## Rule Document Contract

**`docs/__meta__/code.md` is the authority for the `docs/code/` corpus.** Read it before adding or editing a
rule document; this section is a summary and defers to it on every detail. Three prefix specifications narrow
it — `code-principle.md`, `code-pattern.md` and `code-python.md` fix the section outline for `principle-*`,
`pattern-*` and `python-*`. A prefix with none of its own, `test-*` and `logging` today, follows `code.md`.

The shape in brief:

- YAML frontmatter with `name`, `description`, `type` and `scope`, all double-quoted, where `name` is the
  filename without its `.md` extension, and `description` ends with a `Load when …` clause and no period.
- A `## Checklist` section of `- [ ]` items, each verifiable against a diff, followed only by `## References`
  and `## External References`.
- A feature doc is authoritative for documented behaviour: if code and a doc disagree, fix one of them in the
  same change.

Each specification is prose plus the machine-checkable halves beside it — `<stem>.header.json`,
`<stem>.structure.json` and `<stem>.budget.json`, read by the matching `check_<aspect>.py`. The prose is the
authority and the JSON is the same rules in a form a script applies, so **change both in the same commit**:
nothing detects the drift when they disagree. `docs/__meta__/README.md` explains how a document's own path
selects the files that govern it.

## Testing Strategy

The suite is the CLI and nothing else, because nothing else in the library is implemented. It is spread over
the three tiers [test-organization](docs/code/test-organization.md) defines: `tests/unit/test_version.py` for
the version strings, `tests/it/test_cli.py` for the application and its command routing through Typer's
`CliRunner`, and `tests/e2e/test_cli.py` for the installed console script in a subprocess — the only tier that
can observe the `git describe` probe behind `version --verbose`. The vendored check scripts have no tests of
their own; `just check-docs` and `just check-skills` over this repository's own corpus are what exercises
them.

- Run the suite through `just test-unit`, `just test-it`, `just test-e2e` or `just test`, never a bare
  `pytest`. Tier recipes select on markers, so an unmarked test is missed by those recipes; the unfiltered
  `just test` suite still collects it. CI runs `just test`, which runs all three tiers.
- Unit tests cover pure logic — parsing, frontmatter handling, document validation — and do not mock their
  subject or patch module internals. Fixtures for document-shaped inputs are checked in as real files, so a
  test reads the same thing an agent would.
- Every test body is divided by the `#: Given`, `#: When` and `#: Then` markers, with exactly one call
  under `When`. [test-functions](docs/code/test-functions.md) §2 owns the rule and the pytest idioms that
  are awkward to place.
- `--strict-markers` is on. Every marker used must be declared in `pyproject.toml`, with its description.

## Commits

Do not create commits unless the user asks for one. The `commit` skill owns the message format; these rules
cannot be relaxed:

- Conventional Commits format: `type(scope): subject`, signed off with `git commit -s` rather than a
  hand-written trailer; the flag derives it from git config.
- **Never add AI attribution.** No `Co-Authored-By` trailer naming a model or tool, no "generated with" line,
  no session link, and no model or tool name in a commit message, a PR title, a PR body, or a PR comment.
- Do not write the PR number in a commit message; the squash merge appends it. For a single-commit PR, the
  description is the commit body verbatim with the `Signed-off-by:` trailer stripped, and the title is the
  commit title.

## Essential Conventions

- Keep docs and code in sync in the same change.
- **No file holds a version.** `hatch-vcs` derives it from the git tag at build time and the package
  reads it back with `importlib.metadata`; the `code-release` skill owns the release flow. Adding a
  version literal anywhere is a defect, not a convenience.
- Do not add a dependency without a stated reason; this is a small toolkit, and the standard library is
  preferred until it is genuinely insufficient.
- Keep this guide honest: a section describing something that does not exist must say so.
