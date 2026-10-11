---
name: "package-lorecraft-gen"
description: "The lorecraft_gen package's responsibility, publication and import boundary: the private lorecraft-gen package in gen/ that writes the committed generated files, never built or published, which imports lorecraft and is never imported by it, carries no tests and takes its output directory as --outdir. Load when adding or changing a generator, adding a module to gen/, or deciding whether code belongs in lorecraft or in lorecraft_gen"
type: "pkg"
scope: "pkg:lorecraft_gen"
---

# The `lorecraft_gen` Package

## Responsibility

Write the committed generated files from what `lorecraft` declares. It changes when a generated file, or the way
one is rendered into a file, changes.

## Publication

It is never built or published. `lorecraft-gen`, the import package `lorecraft_gen` in `gen/`, is not a member of
the root project's workspace, and neither its environment nor its lock holds it: a `gen-*` recipe installs it on
the fly with `uv run --with-editable ./gen`. It reaches `lorecraft` through a path source to the repository root,
and it is marked `Private :: Do Not Upload`. It has no release, so its version is the fixed `0.0.0` and nothing
derives it from a git tag. The wheel and the source distribution are built from `src/lorecraft/` alone, and the
release workflow publishes those two artifacts.

## Boundary

| Package | It may import this package | This package may import it | Enforced by |
|---|---|---|---|
| `lorecraft` | No | Yes | An import-linter contract, run by `just check` |

## Invariants

- `lorecraft_gen` imports `lorecraft`, and `lorecraft` never imports `lorecraft_gen`.
- A generator restates nothing it renders: a field, a description or an example it needs is added to the type it
  renders, and a page `lorecraft` also prints is rendered by the function `lorecraft` prints it with.
- A generator is one module that runs as `python -m lorecraft_gen.<module>` from the repository root, and a
  `gen-*` recipe is that one `uv run --with-editable ./gen python -m` line, which passes the output directory as
  `--outdir`. The `justfile` variable holds the directory, and the module keeps the same path as its default when
  the option is absent.
- Generation code is internal to the project and carries no tests. The check on a generator is `just gen` leaving
  the tree clean, which CI's `gen-check` job enforces.
- A generator is deterministic and deletes only the stale files named like the ones it writes, such as a rulebook
  page no rule has any more, and leaves any other file in its output directory alone, so `just gen` run twice
  changes nothing, which CI's `gen-check` job relies on.
- A generator's writing functions return the paths they wrote and print nothing; its `main` prints the progress
  lines from what they return.
- The configuration of ruff, ty, pytest, coverage, import-linter and mutmut is the root `pyproject.toml`'s, and
  pytest and coverage do not reach `gen/`; the package keeps only its own packaging tables, such as
  `[tool.uv.sources]` and `[tool.hatch.*]`.

## Examples

```python
# ❌ Bad — the page renderer is copied into the generator: `lorecraft rule` and the committed page disagree the
# first time one of the two changes
def render_rule_page(declaration: RuleDeclaration) -> str:
    return f'# {declaration.code}\n\n{declaration.summary}\n'
```

```python
# ✅ Good — the generator calls the renderer `lorecraft rule` prints with, so there is one page
from lorecraft.cli.rulebook import page_name, render_page


def write_pages(outdir: Path, declarations: Iterable[RuleDeclaration]) -> tuple[Path, ...]:
    paths = []
    for declaration in declarations:
        path = outdir / f'{page_name(declaration)}.md'
        path.write_text(render_page(declaration), encoding='utf-8')
        paths.append(path)
    return tuple(paths)
```

## Checklist

Before committing code, verify:

- [ ] Nothing in `lorecraft` imports `lorecraft_gen`
- [ ] A new generator is a module of `lorecraft_gen`, run by a `gen-*` recipe that is one
      `uv run --with-editable ./gen python -m` line
- [ ] The generator renders content with the function `lorecraft` already prints it with, or with the type it
      renders, and restates no field
- [ ] Its writing function returns the paths and prints nothing
- [ ] No test is added for a generator; running `just gen` twice leaves the tree unchanged
- [ ] Code only a recipe calls is outside `src/lorecraft/`
- [ ] Ruff, ty, pytest, coverage, import-linter and mutmut configuration stays in the root `pyproject.toml`

## References

- [package-lorecraft](package-lorecraft.md) - Companion: The one published package this imports
- [principle-single-responsibility](principle-single-responsibility.md) - Foundation: One reason to change
