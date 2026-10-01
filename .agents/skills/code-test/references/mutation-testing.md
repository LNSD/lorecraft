# Acting on mutation results

A mutation run leaves its results in `mutants/` until the next run. Read them through mutmut:

```bash
uv run mutmut results                  # the mutants that were not killed, one per line
uv run mutmut show <mutant-name>       # one mutant's diff against the source
```

`uv run mutmut browse` is the same in an interactive terminal UI, for a person rather than an agent.

## Statuses

| Status | Meaning |
|---|---|
| `killed` | A test failed with the fault in place. The tests caught it. |
| `survived` | Every test that reaches the code passed with the fault in place. A gap, or an equivalent mutant. |
| `no tests` | No test in the tier ever calls the function. Coverage is missing, not just an assertion. |
| `timeout` | The fault made the tests hang, usually by breaking a loop. Counted as caught by most readings. |
| `suspicious`, `segfault` | The run itself misbehaved. Rerun before reading anything into it. |

`no tests` under `just test-unit-mut` but not under `just test-mut` means only the integration tier reaches
the function. That is fine for wiring; for pure logic it says the unit tests are missing.

## Triage a survivor

Each survivor is one of three things. Decide which before changing anything:

1. **A missing assertion.** The behaviour the fault changes matters, and no test checks it. Write the test
   that fails on the mutant, following the test rules in `docs/code/`: assert on the behaviour a caller sees,
   not on mutmut's diff. One test often kills several survivors in the same function.
2. **An equivalent mutant.** The change cannot alter behaviour: a value nothing reads, a cache that only
   changes speed. Leave it. If it keeps recurring, `# pragma: no mutate` on the line excludes it, with a
   comment saying why the change is invisible.
3. **Dead or redundant code.** Nothing can observe the line because nothing needs it. Remove or simplify
   the code instead of testing it.

Shapes that survive in this repository, and what usually kills them:

- **An error's attributes** — `source`, `__cause__`, a stored value set to `None`. The tests check which
  exception is raised but not what it carries; assert on the attributes a caller reads.
- **Loop control** — `continue` turned into `break`. A test with a second item after the one that takes the
  branch.
- **Literal data** — a schema dict, an example, a key string. Kill it where the literal is a contract, by a
  test that uses it; leave it where it is only illustration.

## Confirm the fix

Rerun on the module alone, by mutant-name glob, and check that the survivor is now killed:

```bash
just test-mut 'lorecraft.<package>.<module>.*'
uv run mutmut results
```

Do not chase a perfect score. The score measures the tests; a test written only to kill a mutant, asserting
on an incidental string or an internal value, makes the suite more brittle without making it stronger.
