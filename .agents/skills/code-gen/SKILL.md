---
name: code-gen
description: Regenerate the committed generated files, such as the JSON Schemas under docs/schemas/ and the rulebook pages under docs/rulebook/, after changing the package types or the rule docstrings they are rendered from, or a gen-* recipe in the justfile. Use after editing such a type or recipe, before running tests or committing, or when CI's `gen-check` job fails with "Generated code is out of date". Not for formatting or linting; see /code-format and /code-check.
compatibility: Requires the just task runner and uv. The generators import the package, so the development environment must be synced first.
allowed-tools: Bash(just gen*) Bash(just sync) Bash(git status *) Bash(git diff *) Bash(grep -n * justfile)
---

# Code Generation Skill

Some files in this repository are generated and committed: the JSON Schemas under `docs/schemas/`, which
editors validate the meta spec files against, and the rulebook pages under `docs/rulebook/`, one per rule
code. Each is rendered from what the package declares, so a change to it leaves the committed file stale until it
is regenerated.

## When to Run

Run `just gen` when a change touches:

- **A type a generator imports.** The generators are the `gen-*` recipes in the `justfile`. Each is a `uv`
  script that imports what it renders from the packages, so its imports are its inputs:

  ```bash
  grep -n '^    from lorecraft' justfile
  ```

  A change to a module those lines import, or to anything that module's types are built from, changes the
  output. Their field docstrings and their `SchemaInfo` metadata are rendered too, so a reworded docstring is
  a change to the output.
- **A rule.** The rulebook generator renders every rule's class: its code, name, release and aliases, and the
  sections of its docstring. A new, renamed or removed rule, or a reworded docstring, changes a page.
- **A `gen-*` recipe itself.**

Nothing else needs it. When unsure, run it: a generator with nothing to change leaves the tree as it was.

## Commands

```bash
just sync   # first, when the environment may be stale: the generators import the package
just gen    # every generator; `just gen-schemas` and `just gen-rulebook` run one alone
```

Then look at what changed, and read the diff as a review of the change that caused it:

```bash
git status --short docs/schemas docs/rulebook
git diff docs/schemas docs/rulebook
```

A description that reads badly in the diff reads badly in an editor too: fix the docstring, not the output. A
rulebook page is generated output too: fix its rule's docstring and regenerate, never the page. No meta spec
governs the pages, so `just check-docs` does not read them; `gen-check` keeps them current.

## Rules

- **Commit the output with the change that caused it.** CI's `gen-check` job runs `just gen` and fails on
  any difference from the committed tree, a new file included.
- **Never edit a generated file by hand.** The next `just gen` undoes it, and CI rejects it before that.
- **A generator restates nothing.** It imports the types it renders; a field, a description or an example
  written into a recipe is a second copy that drifts. Add it to the package's type instead.
- **A schema is rendered from the model that validates the file.** The package deserializes each file with the
  same pydantic model the generator renders, so the schema an editor applies and the check's validation cannot
  disagree about a shape. A test beside each model, such as
  `tests/it/test_structure_spec_schema.py`, holds the committed schema to every file this
  repository writes. When it fails, fix the model or the file. Never loosen the test.

## Where It Fits

Run it after `/code-format` and `/code-check`, and before `/code-test`: the schema tests read the committed
schemas, so a stale one fails them for a reason that has nothing to do with the code under test.

## Common Mistakes to Avoid

- **Fixing a failed `gen-check` job by hand-editing the file** to match what CI printed. Run `just gen`.
- **Running a generator's code another way**, such as a copy of it in a scratch script. The recipe is the one
  place that writes the output, and the one CI checks.

## Next Steps

After regenerating:
1. **Run targeted tests** → use `/code-test`; the schema tests are in the integration tier, `just test-it`
2. **Commit the generated files with the change** → use `/commit`
