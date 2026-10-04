---
name: "tests-e2e"
description: "The end-to-end test framework in tests/lib/: running the installed command in a subprocess, pinning what it prints with one plain-text snapshot file per case and redacting only what differs per build or machine, and writing the repository root it runs over as a `Workspace` that holds only the literals the case turns on. Load when writing or reviewing an end-to-end test, its fixtures or its snapshots, or changing tests/lib/"
type: "core"
scope: "global"
---

# End-to-End Tests

An end-to-end test runs the command a user runs, over a repository a user could have, and compares what it
prints to output a person has read. Its helpers sit in `tests/lib/`, and each one owns one of those three
things: `lib.cli` runs the command, `lib.snapshot` stores what it printed, and `lib.workspace` writes the
repository. This document states how a test uses them. [tests-organization](tests-organization.md) owns the tier
itself, and [tests-functions](tests-functions.md) the shape every test takes.

## 1. Run the Installed Command

A test runs the command through `run_cli`, or `run_alias` for the `lc` alias, never through `subprocess`
directly. Both start the console script the test's own environment installed, by its full path, so a
`lorecraft` earlier on `PATH` is never the one under test, and both stop it after a timeout instead of hanging
the suite.

The command finds its root the way a user's does: from the working directory, passed as `cwd=`, or from
`--root`. Each test states which one its case is about. A test that changes what the command finds on the
machine, such as the `git` it runs, passes the whole environment as `env=` rather than patching the test's own.

## 2. Pin What the Command Prints with a Snapshot

What the command prints for a reader, and the machine-readable document it prints with `--format json`, are each
compared whole to a snapshot: one file per case under `__snapshots__/`, stored as the command printed it, so a
review diff reads like the terminal. `TextSnapshotExtension` stores text and `JsonTextSnapshotExtension` stores
JSON, unparsed. The test binds `expected = snapshot.use_extension(...)` under `#: Given`, guards the exit status
first, and then compares the stream the case is about, with a message that names what the snapshot pins.

A value that differs per build, checkout or machine, such as the version or the absolute root, is swapped for a
placeholder naming it before the comparison, and nothing else is: a placeholder over something the case is
about hides the case. Output a command prints root-relative needs no redaction.

A snapshot changes only with the output it pins, and is reviewed like code; the `code-test` skill owns the
recipes that write and review one.

## 3. Write the Root as a Workspace

A test that runs the command over a repository root it writes declares that root as a `Workspace` and writes it
with one call; a tree the case needs beside the root, such as the directory a link leads out to, is a second
`Workspace` written the same way. Where each part lives is the model's to know, so no test spells a path the
layout fixes. The test lists the parts its case needs and sets only the field under test and every name the
output prints; every field it leaves unset takes a clean default, so the workspace holds the case and nothing
else.

The checked-in `tests/e2e/fixtures/workspace/` is the one root a test does not write: a realistic tree a reader
can open beside the snapshots of commands that draw a whole repository.

## 4. Declare the Workspace in `#: Given`

The workspace is one expression, short enough to read in the test whose name states its case, so it sits inline
under `#: Given`. One that several tests share moves into a fixture, whose docstring states the case alone,
never the clean parts around it.

```python
# ❌ Bad — the case, an absolute link, is one line in a skill written out path by path
skill_directory = tmp_path / '.agents' / 'skills' / 'review'
skill_directory.mkdir(parents=True)
(skill_directory / 'SKILL.md').write_text(
    '---\nname: review\ndescription: Review a change\n---\n\n# Review\n\nRead [the steps](/steps.md).\n',
    encoding='utf-8',
)
```

```python
# ✅ Good — the body is the case; the frontmatter takes a clean default, and the snapshot pins the finding
#: Given
expected = snapshot.use_extension(TextSnapshotExtension)
workspace = Workspace(skills=[Skill('review', body='# Review\n\nRead [the steps](/steps.md).\n')])
root = workspace.write(tmp_path, faker)
arguments = ('check', 'skills', '--root', str(root))

#: When
result = run_cli(*arguments)

#: Then
assert result.returncode == 1, result.stderr
assert result.stdout == expected, 'the link-absolute finding matches the reviewed snapshot'
```

## Checklist

Before committing code, verify:

- [ ] Every end-to-end test runs the command through `run_cli` or `run_alias`
- [ ] Every printed output a case is about, text or JSON, is compared whole to a snapshot of its own
- [ ] Only what differs per build, checkout or machine is redacted, each to a placeholder naming it
- [ ] Every snapshot that changed is reviewed and committed with the output change that moved it
- [ ] Every repository root a test writes, and any tree beside it, comes from a `Workspace` in one call
- [ ] No end-to-end test spells a path the workspace layout fixes
- [ ] A workspace sets only the field under test and the names the output prints
- [ ] A workspace sits inline under `#: Given` unless several tests share it, and a shared fixture's docstring
      states the case alone

## References

- [tests-organization](tests-organization.md) - Related: Owns the end-to-end tier, its directory and its marker
- [tests-functions](tests-functions.md) - Related: Owns the Given, When and Then every end-to-end test follows, and fixture scope
- [tests-assertions](tests-assertions.md) - Related: Owns the message on each assertion and the exit-status guard
- [principle-information-hiding](principle-information-hiding.md) - Foundation: The layout is the model's to know, not each test's

## External References

- [syrupy — Snapshot testing for pytest](https://github.com/syrupy-project/syrupy)
- [Faker — Pytest fixtures](https://faker.readthedocs.io/en/master/pytest-fixtures.html)
