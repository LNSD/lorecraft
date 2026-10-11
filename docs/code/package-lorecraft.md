---
name: "package-lorecraft"
description: "The lorecraft package's responsibility, publication and import boundary: the one package built and published, which never imports a private package and ships no generation or test-tier code. Load when adding code to the published package, adding a dependency or an entry point to it, or deciding whether code belongs in lorecraft or in a private package"
type: "pkg"
scope: "pkg:lorecraft"
---

# The `lorecraft` Package

## Responsibility

Hold what a user installs: the commands, the checks they run and the model the checks read. It changes when a
command, a check or a specification dialect changes.

## Publication

It is the only package built and published. The wheel holds `src/lorecraft/` and the source distribution holds that
directory and its metadata files, so a package beside it does not reach a user. The unit tests co-located under
`src/lorecraft/**/tests/` are excluded from both, which is what lets a test import `pytest` without making it a
dependency.

The layers inside it, and what each may import, are the business of the `module-*` documents: this
document owns the line around the package as a whole.

## Boundary

| Package | It may import this package | This package may import it | Enforced by |
|---|---|---|---|
| `lorecraft_gen` | Yes: it renders what `lorecraft` declares | No | An import-linter contract, run by `just check` |
| `tests/it`, `tests/e2e`, `tests/lib` | Yes: they exercise it as a user imports it | No, outside a `tests/` subpackage | No gate; review |

## Invariants

- Nothing in `lorecraft` imports a private package, so none of its code reaches the wheel. The import-linter
  contract that forbids `lorecraft_gen` is run by `just check`.
- No module outside a `tests/` subpackage imports a test tier. The test tiers under `tests/` are test code, not a
  package: `tests/lib` is put on the import path by pytest's `pythonpath`. A unit test in a `tests/` subpackage
  may import it, and no gate enforces the rest, so review does.
- Code whose only caller is a recipe, a test or a workflow is not part of `lorecraft`: it belongs to a private
  package.
- A module is part of `lorecraft` because a command or a layer below it uses it, never because it holds the types
  a private package renders.
- The configuration of ruff, ty, pytest, coverage, import-linter and mutmut is the root `pyproject.toml`'s, and
  pytest and coverage do not reach `gen/`; a private package keeps only its own packaging tables, such as
  `[tool.uv.sources]` and `[tool.hatch.*]`.

## Examples

```python
# ❌ Bad — a command imports a generator to offer `lorecraft gen`: the generator ships in the wheel, and the
# command fails for every user who did not install the repository's private packages
from lorecraft_gen.schemas import main as write_schemas


def gen() -> None:
    write_schemas()
```

```python
# ✅ Good — the generator is a module a recipe runs; the published package has no command that reaches it
# justfile: gen-schemas
#     uv run --with-editable ./gen python -m lorecraft_gen.schemas --outdir {{GEN_SCHEMAS_OUTDIR}}
```

## Checklist

Before committing code, verify:

- [ ] Nothing under `src/lorecraft/` imports `lorecraft_gen`, and no module outside a `tests/` subpackage imports a
      test tier
- [ ] New code lives in `lorecraft` only because a command or a layer below it uses it
- [ ] Nothing a private package needs is added to the wheel or the source distribution
- [ ] No ruff, ty, pytest, coverage, import-linter or mutmut configuration is added beside the root `pyproject.toml`

## References

- [principle-single-responsibility](principle-single-responsibility.md) - Foundation: One reason to change
- [package-lorecraft-gen](package-lorecraft-gen.md) - Companion: The private package that imports this one and is never published
