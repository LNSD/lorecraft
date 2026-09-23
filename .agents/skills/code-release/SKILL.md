---
name: "code-release"
description: "Cut a release of the package: bump the version, build the source distribution and the wheel, and verify what the artifacts actually contain before tagging. Use when preparing a release, bumping the version, building distributions, or checking that packaging metadata is correct"
compatibility: "Requires the just task runner and uv. hatchling builds the artifacts through uv, so no build backend is installed by hand. Publishing to an index is NOT configured in this repository, so this skill ends at a verified artifact and a tag."
allowed-tools: Bash(just build *) Bash(just clean *) Bash(just fmt-check *) Bash(just check *) Bash(just typecheck *) Bash(just test *) Bash(just check-docs *) Bash(just check-skills *) Bash(git status *) Bash(git log *) Bash(git tag *)
---

# Code Release Skill

Packaging for this repository, a Python package built with uv and hatchling.

A release here is four steps: bump one line, build, verify what was built, tag. The build itself is a
single recipe, so the work that matters is the verification either side of it.

## Prerequisite

**Every gate must be green on the commit being released, not on a dirty tree.** These are the same
checks CI runs, in the same order:

```bash
just fmt-check && just check && just typecheck && just test && just check-docs && just check-skills
```

If any of them fails, go back to the skill that owns it: `/code-format`, `/code-check`, `/code-test`,
`/docs-rules-check`, `/skills-check`. A release built from a tree that fails its own document checks
publishes documents this project says are invalid.

Also confirm the working tree is clean and the release is being cut from the intended branch:

```bash
git status --porcelain     # must print nothing
git log --oneline -1
```

## The version has one home

`__version__` in `src/lorewright/__init__.py` is the only place the version is written. `pyproject.toml`
declares `dynamic = ["version"]` and `[tool.hatch.version]` reads it from that file, so a bump is one
line and the manifest cannot disagree with the package.

```python
__version__ = '0.2.0'
```

Do not add a second version string anywhere. If you find one, delete it rather than syncing it.

## Commands

| Command | Purpose |
|---|---|
| `just clean` | Remove `dist/`, caches and `__pycache__` before a build |
| `just build` | `uv build`: writes a source distribution and a wheel into `dist/` |

Always clean first. `uv build` does not empty `dist/`, so a stale wheel from an earlier version sits
next to the new one and is easy to upload or inspect by mistake.

```bash
just clean
just build
ls -la dist/
```

Two files should appear, and only two:

```
dist/lorewright-<version>.tar.gz            source distribution
dist/lorewright-<version>-py3-none-any.whl  wheel
```

## Verify the artifacts

A green build says the metadata parsed. It does not say the right files went in. Check both artifacts
before tagging.

### The wheel

```bash
python3 -c "import zipfile,sys;[print(n) for n in zipfile.ZipFile(sys.argv[1]).namelist()]" dist/*.whl
```

It must contain, and contain nothing beyond:

- `lorewright/` and everything under it, and no other top-level package
- `lorewright-<version>.dist-info/licenses/LICENSE-MIT` and `LICENSE-APACHE`, because the project is
  dual licensed and `license-files` in `pyproject.toml` puts both in the artifact
- `METADATA`, `WHEEL`, `RECORD`

Read the metadata and confirm the version is the one just bumped, and that the licence expression
survived:

```bash
python3 -c "import zipfile,sys;z=zipfile.ZipFile(sys.argv[1]);print(z.read([n for n in z.namelist() if n.endswith('METADATA')][0]).decode()[:400])" dist/*.whl
```

`Version:` must match `__version__`. `License-Expression: MIT OR Apache-2.0` and both `License-File:`
lines must be present.

### The source distribution

```bash
tar tzf dist/*.tar.gz | sed 's|^[^/]*/||' | cut -d/ -f1 | sort -u
```

The sdist carries only what is needed to build the package from source: `src/lorewright/`,
`pyproject.toml`, `README.md` and the two licence files. Everything else in the repository, `docs/`,
`tests/`, `.agents/`, `.github/`, `justfile` and `uv.lock`, is repository material rather than package
material, and is excluded by the `include` list in `[tool.hatch.build.targets.sdist]`.

`tests/` is the one worth revisiting. A downstream packager builds from the sdist and runs its suite to
verify the build, and cannot do that when the tests are absent. Add `"/tests"` back the day someone
packages this project.

Expect exactly that listing. Anything else means an `include` pattern lost its leading slash: the
patterns are gitignore-style, so an unanchored `README.md` also matches `docs/__meta__/README.md` and
drags a directory back in.

### Known packaging gap

`README.md` is the long description, and it opens with `<img src="docs/assets/logo-*.png">` and links
written relative to the repository. GitHub resolves those; an index rendering the long description
does not, so the logo and the relative links break there. Fix it by making those URLs absolute before
the first upload, not after.

## Tag

Tag only after the artifacts are verified.

```bash
git tag -a v<version> -m "v<version>"
git tag -l --sort=-v:refname | head -3
```

Do not push a tag as part of this skill. Pushing is the owner's call, and a tag that exists only
locally can still be deleted.

## Publishing is not configured

There is no `publish` recipe, no index credentials, no trusted publisher and no release workflow in
`.github/workflows/`. CI runs the gates on `main` and on pull requests, and nothing in it uploads
anything.

When publishing is set up, the command is `uv publish`, and the release workflow should build from a
tag and upload with a trusted publisher rather than a long-lived token. Until then, do not invent the
step: report that the artifact is built, verified and tagged, and stop.

## Anti-patterns

- Building from a dirty tree, or from a tree whose document and skill checks fail.
- Bumping the version in more than one file, or editing `version` in `pyproject.toml`, which no longer
  holds it.
- Running `just build` without `just clean` and then reading a stale artifact from `dist/`.
- Treating a successful build as a verified artifact. Read the wheel contents.
- Tagging before the artifacts are checked, or pushing a tag without being asked.
- Running `uv publish`, or adding a token to the repository, on the assumption that publishing is
  wanted. It is not configured, and configuring it is not this skill's job.
- Committing `dist/`. It is ignored, and it should stay ignored.

## Next Steps

After a verified build and a local tag:

1. **Report** the version, both artifact filenames, and what the wheel contained.
2. **Ask** before pushing the tag or opening a release.
