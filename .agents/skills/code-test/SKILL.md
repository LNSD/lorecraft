---
name: code-test
description: Run targeted tests after format and lint are green. Defaults to the unit tier; widens to the integration, end-to-end or whole suite only on explicit signals. Use after editing Python code under src/ or tests/, or when the user asks to run tests. Also measures coverage, which lines and branches each tier runs, when asked what the tests reach; and runs mutation testing, an expensive run that scores how effective the tests are at catching faults, only when asked how strong the tests are or whether they pin what they claim. No tier here needs a container, an external service, or credentials.
compatibility: Requires the just task runner and uv. pytest is invoked through the project environment rather than a system install. Nothing else is needed — this repository has no container-backed, networked or credentialed tests.
allowed-tools: Bash(just test-unit *) Bash(just test-it *) Bash(just test-e2e *) Bash(just test *) Bash(just test-cov *) Bash(just test-unit-cov *) Bash(just test-it-cov *) Bash(just test-e2e-cov *) Bash(just test-cov-report *) Bash(just test-mut *) Bash(just test-unit-mut *) Bash(just test-it-mut *) Bash(just test-mut-report *) Bash(uv run mutmut results*) Bash(uv run mutmut show *) Bash(just snapshot-review) Bash(uv run pytest src/*) Bash(uv run pytest tests/*)
---

# Code Testing Skill

Runs this repository's pytest suite through the justfile.

## Prerequisite

**`/code-format` and `/code-check` must be green first.** If lint is dirty, go back to `/code-check`:
an unused import or an undefined name is cheaper to surface there than through a test run, and a
failing collection tells you less than a lint message about the same mistake.

## Scope Selection

Pick the first row whose **blast radius** covers the change — the set of code paths a mistake here
could plausibly break. Rows below it are escalations; take one only when a signal pushes the radius
outward.

| Blast radius | Command |
|---|---|
| None (docs, comments, rule documents only) | Skip; state why |
| Pure logic — a dataclass, a helper, one check, one parser | `just test-unit` |
| A CLI command, a module seam, wiring several units together | `just test-unit` then `just test-it` |
| Packaging, the console script, the entry point, anything the installed artifact exposes | `just test-e2e` |
| Shared types, a base class, the registry, an `__init__.py` that re-exports | `just test` |

**Signals that push the radius outward, from "pure logic" to wider:**
- Changed a signature, an attribute, or the semantics of a type that other modules import — a
  finding, a check result, a parsed document.
- Changed a shared type that more than one module depends on, or anything one layer
  imports from another.
- Changed a registry, discovery of checks, or an `__init__.py` that re-exports.
- Changed a `pyproject.toml` — the root's dependency groups, pytest configuration or marker list, or a
  package's dependencies, console script, or how its version is derived. The last two reach
  `tests/e2e/` and nothing below it.

If none fire, unit tests are enough.

### Marker traps

Tests are selected by marker, and `--strict-markers` is on. Two consequences worth knowing before
you filter:

- **An undeclared marker is a collection error, not a skip.** Adding `@pytest.mark.slow` without a
  matching entry in `[tool.pytest.ini_options] markers` fails the whole run at collection, and a
  command selecting `-m slow` fails before a single test executes. `unit`, `it` and `e2e` are the
  markers declared today; adding another means editing the root `pyproject.toml` in the same change.
- **`just test-unit` filters on the marker, not on the directory.** A test placed in a unit `tests/`
  subpackage without `@pytest.mark.unit` is invisible to `just test-unit` and runs only under `just test`. If a
  new test never seems to execute, check its marker before you doubt the assertion.

## Commands

| Command | Purpose |
|---|---|
| `just test-unit` | **Default.** Marker `unit`. Pure logic, nothing beyond the interpreter. |
| `just test-it` | Marker `it`. The package's own modules wired together, in process. |
| `just test-e2e` | Marker `e2e`. The installed console script, in a subprocess. |
| `just test` | Every tier, no marker filter. Alias: `just test-all`. |

Every recipe takes extra flags, passed through to pytest — each tier recipe is implemented as a
dependency on `test`, so `just test-unit` runs `uv run pytest -m unit` with your flags appended. For a
single file or a single test — which no recipe covers — call pytest directly:

```bash
uv run pytest src/lorecraft/<pkg>/tests/test_<module>.py -v
uv run pytest tests/it/test_<module>.py::Test<Subject>::test_<case> -v
uv run pytest tests/e2e/test_<module>.py -v
```

### Snapshots

A snapshot test, through syrupy's `snapshot` fixture, compares output to a file checked in under
`__snapshots__/` beside its test module; `tests/lib/snapshot.py` stores each one as plain text. Command output
is pinned this way, with whatever varies per build or machine, such as the version or the workspace root,
swapped for a placeholder before it is compared. Every recipe above fails on a mismatch, and on a snapshot no
test reads any more.

| Command | Purpose |
|---|---|
| `just snapshot-update` | Write or refresh every snapshot and delete the unused ones. Runs the whole suite. |
| `just snapshot-review` | Show which snapshot files changed and their diff since the last commit. |

A failing snapshot is a finding, not a chore: when output changed on purpose, run `just snapshot-update`,
read `just snapshot-review`, and commit the snapshot with the change. Never update to turn a run green
without reading the diff. Updating one tier alone reads the other tiers' snapshots as unused, so the recipe
never filters.

## Coverage

Coverage says which lines and branches a tier runs — not whether a test checks what they do; that is
[mutation testing](#mutation-testing)'s question. It costs one ordinary run of the tier, so measure it when
asked what the tests reach, or to find the code no test runs before writing tests for a module.

| Command | Purpose |
|---|---|
| `just test-cov` | Every tier together: the suite's coverage. |
| `just test-unit-cov` | The unit tier alone: the pure logic its own tests reach. |
| `just test-it-cov` | The integration tier alone. |
| `just test-e2e-cov` | The e2e tier alone, measured inside the console script's subprocess. |
| `just test-cov-report [TITLE]` | The last run as Markdown: the total, and the files below full coverage. |

Each run overwrites `.coverage`. `uv run coverage report` reads it again, with the missing lines per file;
`uv run coverage html` writes a browsable copy to `htmlcov/`. CI runs all four on every pull request and
posts the report as one comment; it never fails the build.

## Mutation testing

**Expensive, and never the check after an edit.** mutmut injects small faults into `src/lorecraft/` — a
flipped comparison, a changed constant, a dropped argument — and runs the tier once per fault. A fault the
tests catch is *killed*; one they miss *survives*. The share killed is how effective the tests are, which line
coverage cannot tell you: a line can run under a test that asserts nothing about it.

Run it when the user asks how strong the tests are, before hardening a module's tests, or to confirm new tests
pin the behaviour they claim to. It costs minutes and every core.

| Command | Purpose |
|---|---|
| `just test-mut` | Against the unit and integration tiers together: the suite's score. |
| `just test-unit-mut` | Against the unit tier alone: what the unit tests pin without help. |
| `just test-it-mut` | Against the integration tier alone. |
| `just test-mut-report [TITLE]` | The last run as Markdown: the score, survivors per module, a sample of diffs. |

Mutant names, as globs, narrow a run to one module: `just test-mut 'lorecraft.vfs.disk.*'`. Each run starts
from an empty `mutants/`. The e2e tier has no recipe: it runs the console script in a subprocess, where
mutmut cannot swap a fault in. CI runs `just test-mut` alone on every pull request and posts the report as
one comment; it never fails the build.

Read [references/mutation-testing.md](references/mutation-testing.md) before acting on a surviving mutant.

## Notes

Unit tests sit beside the module they test, in a `tests/` subpackage under `src/`: the tests
for `<pkg>/<module>.py` are `<pkg>/tests/test_<module>.py`, and no wheel or sdist ships them. The `it`
tier lives flat, in `tests/it/`.
[test-organization](../../../docs/code/test-organization.md) §2 owns the placement.
The end-to-end tier lives in `tests/e2e/` and covers the command line only: it drives the installed
`lorecraft` console script. Its shared helpers live beside the suites in `tests/lib/`, imported as
`lib` (`from lib.cli import run_cli`) through pytest's `pythonpath = ["tests"]`. A library layer has no
e2e tier, because its end-to-end surface is its public API, which its `it` tier already covers.
`tests/e2e/` is the slowest by an order of magnitude and the only tier that spawns a process, which is
the reason the default stays narrow.

pytest exits 5 when it collects nothing, and the `test` recipe preserves that failure. A tier with
no collected tests therefore fails instead of reporting a misleading green run.

Collection is confined by `testpaths` to `src/`, `tests/it/` and `tests/e2e/`. A unit `tests/` subpackage
has an `__init__.py`, so `--import-mode=importlib` imports it under its real dotted name and its relative imports resolve; the `it` and `e2e` directories carry none,
and importlib mode keeps two test files of the same name apart. Document-shaped fixtures are checked in as real
files, so a test reads the same thing an agent would; adding a fixture file changes no configuration,
but the test that consumes it still needs its marker.

## Anti-patterns

- Running tests before `/code-check` is green.
- Reaching for `just test` when the change is pure logic — use `just test-unit`.
- Putting a test that spawns a process, or one that needs the package installed, anywhere but
  `tests/e2e/`. [test-organization](../../../docs/code/test-organization.md) owns the tier boundaries.
- Introducing a marker without declaring it in the root `pyproject.toml`.
- Calling `pytest` outside `uv run` — it is not installed in a system interpreter.
- Reading a zero-collected run as a passing run.
- Skipping tests on a behaviour change. Docs-only is the one acceptable skip, and it should be stated.

## Debugging

Append pytest flags to either recipe: `-x` to stop at the first failure, `-k <expr>` to select by
name, `--log-cli-level=DEBUG` to surface log output, `-s` to let prints through.

```bash
just test-unit -k <name-fragment> --log-cli-level=DEBUG -x
```

`--log-cli-level` works on the module-level loggers described in
[docs/code/logging.md](../../../docs/code/logging.md); a module that logs through
`logging.getLogger(__name__)` is reachable by name, and one that does not is not.

## Next Steps

After tests pass: review the diff and commit, with lint and tests green.
