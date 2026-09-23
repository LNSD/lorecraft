---
name: code-test
description: Run targeted tests after format and lint are green. Defaults to the unit tier; widens to the whole suite only on explicit signals. Use after editing Python code under src/ or tests/, or when the user asks to run tests. No tier here needs a container, an external service, or credentials.
compatibility: Requires the just task runner and uv. pytest is invoked through the project environment rather than a system install. Nothing else is needed — this repository has no container-backed, networked or credentialed tests.
allowed-tools: Bash(just test-unit *) Bash(just test *) Bash(uv run pytest tests/unit/*)
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
| Shared types, a base class, the registry, an `__init__.py` that re-exports | `just test` |

**Signals that push the radius outward, from "pure logic" to wider:**
- Changed a signature, an attribute, or the semantics of a type that other modules import — a
  finding, a check result, a parsed document.
- Changed a shared type under `src/lorewright/` that more than one check depends on.
- Changed a registry, discovery of checks, or an `__init__.py` that re-exports.
- Changed `pyproject.toml` — dependency groups, pytest configuration, or the marker list.

If none fire, unit tests are enough.

### Marker traps

Tests are selected by marker, and `--strict-markers` is on. Two consequences worth knowing before
you filter:

- **An undeclared marker is a collection error, not a skip.** Adding `@pytest.mark.slow` without a
  matching entry in `[tool.pytest.ini_options] markers` fails the whole run at collection, and a
  command selecting `-m slow` fails before a single test executes. `unit` is the only marker
  declared today; adding another means editing `pyproject.toml` in the same change.
- **`just test-unit` filters on the marker, not on the directory.** A test placed in `tests/unit/`
  without `@pytest.mark.unit` is invisible to `just test-unit` and runs only under `just test`. If a
  new test never seems to execute, check its marker before you doubt the assertion.

## Commands

| Command | Purpose |
|---|---|
| `just test-unit` | **Default.** Marker `unit`. Fast, no external dependencies. |
| `just test` | The whole suite, no marker filter. Alias: `just test-all`. |

Both recipes take extra flags, passed through to pytest — `just test-unit` is implemented as a
dependency on `test`, so it runs `uv run pytest -m unit` with your flags appended. For a single file
or a single test — which no recipe covers — call pytest directly:

```bash
uv run pytest tests/unit/test_<module>.py -v
uv run pytest tests/unit/test_<module>.py::Test<Subject>::test_<case> -v
```

## Notes

No test is written yet — there is nothing implemented to test — so `just test-unit` and `just test`
currently select the same empty set. That is a fact about today's tree, not a reason to reach for
`just test` by default: keep the narrower command as the habit so it stays meaningful once the suite
and a second marker exist.

pytest exits 5 when it collects nothing. The `test` recipe turns that exit code into success, so an
empty or fully filtered-out selection reports "no tests ran" and still exits 0. Read the collection
line before trusting a green run: zero collected tests is a green exit that proves nothing.

Collection is confined to `tests/` by `testpaths`. Document-shaped fixtures are checked in as real
files, so a test reads the same thing an agent would; adding a fixture file changes no configuration,
but the test that consumes it still needs its marker.

## Anti-patterns

- Running tests before `/code-check` is green.
- Reaching for `just test` when the change is pure logic — use `just test-unit`.
- Introducing a marker without declaring it in `pyproject.toml`.
- Calling `pytest` outside `uv run` — it is not installed in a system interpreter.
- Reading a zero-collected run as a passing run.
- Skipping tests on a behaviour change. Docs-only is the one acceptable skip, and it should be stated.

## Pre-approved commands

Runnable without asking: `just test-unit`, `just test`, and `uv run pytest tests/unit/...` for a
single file or test. Nothing in this suite starts a service or spends credentials, so there is no
tier that needs confirmation first.

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
