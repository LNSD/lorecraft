---
name: "code-release"
description: "Cut a release of the package: tag the commit, build the source distribution and the wheel from that tag, and verify what the artifacts actually contain. Use when preparing a release, bumping the version, building distributions, or checking that packaging metadata is correct"
compatibility: "Requires the just task runner, uv, a working GPG signing key because every tag and commit is signed, and git with the repository's full history: hatch-vcs reads the version from `git describe`, so a shallow or tagless checkout builds a version that is not the release. Publishing to an index is NOT configured in this repository, so this skill ends at a tag and a verified artifact."
allowed-tools: Bash(just build *) Bash(just clean *) Bash(just fmt-check *) Bash(just check *) Bash(just typecheck *) Bash(just test *) Bash(just check-docs *) Bash(just check-skills *) Bash(git status *) Bash(git log *) Bash(git tag *) Bash(git describe *)
---

# Code Release Skill

Packaging for this repository, a Python package built with uv and hatchling.

A release here is four steps: tag the commit, build, verify what was built, and delete the tag if the
artifacts are wrong. The build itself is a single recipe, so the work that matters is the verification
either side of it.

**The tag comes first, and that is the one ordering constraint.** The version is derived from the tag
at build time, so building before tagging produces an artifact labelled with a development version
(`0.2.dev3+g93b1ed1fb`) rather than the release.

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

## Everything a release stands on is signed

**Every tag is GPG-signed, and so is every commit it points at.** A tag is what the version is derived
from and what a consumer resolves a release by, so an unsigned tag is an unauthenticated claim about
which code is `v<version>` — and anyone with push access can move it.

- Tags: `git tag -s`. Never `git tag -a`, which annotates without signing, and never a bare
  `git tag v<version>`, which is a lightweight tag carrying no author, no date and no signature.
- Commits: `commit.gpgsign` is set in the owner's git configuration, so `git commit -s` produces a
  commit that is both GPG-signed and DCO signed-off. The two are different things and a release needs
  both; the `commit` skill owns the sign-off trailer.

Check the commit being released before tagging it:

```bash
git log -1 --show-signature     # must report a good signature on the release commit
```

An unsigned commit is not fixed by signing the tag over it. Re-sign it with `git commit --amend -s`
before tagging, or cut the release from a commit that is signed.

## The version has one home, and it is the git tag

No file in the tree holds a version. `pyproject.toml` declares `dynamic = ["version"]` and
`[tool.hatch.version]` sets `source = "vcs"`, so hatch-vcs runs `git describe` at build time. Bumping
the version *is* tagging:

```bash
git tag -s v0.2.0 -m "v0.2.0"
```

What each state builds as, under the `node-and-date` local scheme:

| Tree state | Built version |
|---|---|
| Exactly on tag `v0.2.0`, clean | `0.2.0` |
| Three commits past `v0.2.0`, clean | `0.2.1.dev3+g93b1ed1fb` |
| Any of the above with uncommitted changes | the same, plus `.d<date>`, e.g. `+g93b1ed1fb.d20260923` |

A `+`-suffixed local version is a development build. It is legitimate to hand someone, and PyPI will
refuse it, which is the intended safety net.

At runtime the package reports what it was built with, via `importlib.metadata` in
`src/lorecraft/_metadata.py`. `lorecraft version --verbose` additionally runs
`git describe --tags --always --dirty` when it is running from a checkout, so a developer's install
shows the working tree it is actually sitting on rather than the version frozen at install time.

Do not add a version string anywhere. If you find one, delete it rather than syncing it.

## Tag, then build

Tag the commit the release is cut from, before anything is built:

```bash
git tag -s v<version> -m "v<version>"
git describe --tags --dirty     # must print exactly v<version>, with no -dirty suffix
git tag -v v<version>            # must report a good signature
```

`-s`, never `-a` and never a bare `git tag v<version>`. A `-dirty` suffix or a `-<n>-g<sha>` suffix
from `git describe` means the tag is not on the commit being built, and every artifact below will
carry a development version.

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
dist/lorecraft-<version>.tar.gz            source distribution
dist/lorecraft-<version>-py3-none-any.whl  wheel
```

## Verify the artifacts

A green build says the metadata parsed. It does not say the right files went in. Check both artifacts
before the tag is pushed or the wheel is handed to anyone.

### The wheel

```bash
python3 -c "import zipfile,sys;[print(n) for n in zipfile.ZipFile(sys.argv[1]).namelist()]" dist/*.whl
```

It must contain, and contain nothing beyond:

- `lorecraft/` and everything under it, and no other top-level package
- `lorecraft-<version>.dist-info/licenses/LICENSE-MIT` and `LICENSE-APACHE`, because the project is
  dual licensed and `license-files` in `pyproject.toml` puts both in the artifact
- `METADATA`, `WHEEL`, `RECORD`

Read the metadata and confirm the version is the one just tagged, and that the licence expression
survived:

```bash
python3 -c "import zipfile,sys;z=zipfile.ZipFile(sys.argv[1]);print(z.read([n for n in z.namelist() if n.endswith('METADATA')][0]).decode()[:400])" dist/*.whl
```

`Version:` must be the tag without its `v` prefix, and must carry no `+` local segment — a `+g<sha>`
or `.d<date>` suffix means the build did not happen on the tagged commit, or happened on a dirty tree.
`License-Expression: MIT OR Apache-2.0` and both `License-File:` lines must be present.

### The source distribution

```bash
tar tzf dist/*.tar.gz | sed 's|^[^/]*/||' | cut -d/ -f1 | sort -u
```

The sdist carries only what is needed to build the package from source: `src/lorecraft/`,
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

## After verifying

```bash
git tag -l --sort=-v:refname | head -3
```

Do not push a tag as part of this skill. Pushing is the owner's call, and a tag that exists only
locally can still be deleted. If the artifacts are wrong, delete the tag with
`git tag -d v<version>`, fix the cause, and tag again — a tag that was never pushed costs nothing to
withdraw.

## Publishing is not configured

There is no `publish` recipe, no index credentials, no trusted publisher and no release workflow in
`.github/workflows/`. CI runs the gates on `main` and on pull requests, and nothing in it uploads
anything.

When publishing is set up, the command is `uv publish`, and the release workflow should build from a
tag and upload with a trusted publisher rather than a long-lived token. Until then, do not invent the
step: report that the artifact is built, verified and tagged, and stop.

## Anti-patterns

- Building from a dirty tree, or from a tree whose document and skill checks fail. The version says so
  now, but the artifact is still wrong.
- Building before tagging, and then reading the development version off the artifact as if it were the
  release.
- Writing a version into a file, or editing `version` in `pyproject.toml`. The tag holds it.
- Building from a shallow clone or a checkout whose tags were never fetched: `git describe` cannot see
  the tag, and the version silently comes out as a development version off an older one.
- Tagging with `git tag -a` or `git tag v<version>`. Both produce an unsigned tag, and the second
  produces a lightweight one that records nothing at all.
- Tagging a commit that is not itself signed, or signing the tag and skipping the DCO sign-off on the
  commit.
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
