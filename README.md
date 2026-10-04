<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/lnsd/lorecraft/main/docs/assets/logo-dark.png" />
  <img src="https://raw.githubusercontent.com/lnsd/lorecraft/main/docs/assets/logo-light.png" alt="lorecraft" width="120" />
</picture>

# lorecraft

[Read the Docs](https://github.com/lnsd/lorecraft/tree/main/docs) · [Report Bug](https://github.com/lnsd/lorecraft/issues/new?labels=bug) · [Request Feature](https://github.com/lnsd/lorecraft/issues/new?labels=enhancement)

[![CI](https://img.shields.io/github/actions/workflow/status/lnsd/lorecraft/ci.yml?branch=main&label=CI)](https://github.com/lnsd/lorecraft/actions/workflows/ci.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://github.com/lnsd/lorecraft/blob/main/LICENSE-APACHE)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/lnsd/lorecraft/blob/main/LICENSE-MIT)
[![PyPI](https://img.shields.io/pypi/v/lorecraft)](https://pypi.org/project/lorecraft/)

</div>

A toolkit for the agent-facing documentation of a repository: the coding rules, feature docs and
skills that agents read while they work.

Lorecraft keeps that documentation consistent as it grows. A repository declares the shape each kind
of document must have, and Lorecraft checks every document against it, locally or in CI. It checks the
repository's agent skills too, against the [Agent Skills specification](https://agentskills.io/specification).
Its own agent skills cover the rest, guiding an agent as it writes and reviews those documents.

## Installation

With [uv](https://docs.astral.sh/uv/), install the `lorecraft` command as a tool, or run it on demand without
installing it:

```sh
uv tool install lorecraft
uvx lorecraft check
```

To pin it to a uv project instead, add it as a development dependency and run it through the project's
environment:

```sh
uv add --dev lorecraft
uv run lorecraft check
```

Or install it in an isolated environment with [pipx](https://pipx.pypa.io/):

```sh
pipx install lorecraft
```

Confirm which build you are running with `lorecraft version`. Every command also runs as `lc`, a shorter
name for `lorecraft`.

<details>
<summary>Installing from the Git repository</summary>

To run a commit that has not been released yet, install from the repository:

```sh
uv tool install "git+https://github.com/lnsd/lorecraft"
```

`pipx install` takes the same URL. It builds from the default branch. Append `@<tag>`, `@<branch>` or `@<commit>` to the repository URL to
install a specific revision instead. The version is derived from the repository's git tags, so a build between
two releases reports a development version, such as `0.2.1.dev3+g93b1ed1fb`.

</details>

## Quickstart

Write your coding rules as documents in `docs/code/`, and describe what a rule document looks like in
`docs/__meta__/`:

```
docs/
├── __meta__/
│   ├── code.md                     # what every rule document looks like, in prose
│   ├── code.structure.json         # its frontmatter, sections, word caps and token budget
│   ├── code-python.md              # narrower rules for the python-* documents
│   └── code-python.structure.json  # the frontmatter and sections they add
└── code/
    ├── logging.md                  # governed_by: [code]
    ├── python-modules.md           # governed_by: [code, code-python]
    ├── python-typing.md            # governed_by: [code, code-python]
    └── tests-functions.md          # governed_by: [code]
```

Each specification is a pair of files that share a specification name, such as `code`: the prose,
`<name>.md`, and the structure specification, `<name>.structure.json`, which the checks apply. `code` governs
every document in `docs/code/`, and `code-python` adds its rules to the `python-*` documents.

Keep the rule documents in shape, from the repository root:

```sh
lorecraft inspect  # which specifications govern which rule document
lorecraft check    # check every rule document against them, and every agent skill
```

`lorecraft check` exits 0 when it finds nothing, 1 when it reports findings, and 2 when it could not run, so it
can gate a CI job as it is. Both commands take `--format json` for a script to read.

Then let your agent use them, through the [skills](#skills): `/code-rules` loads the rules that apply before it writes code, and
`/code-rules-check` checks its changes against them. This repository's own [`docs/code/`](https://github.com/lnsd/lorecraft/tree/main/docs/code) is a
working example.

## Skills

The [`skills/`](https://github.com/lnsd/lorecraft/tree/main/skills) directory holds agent skills that put the rules to work:

- **During development**, `code-rules` loads the coding rules that apply before the agent writes code,
  and `docs-rules` does the same for your documents.
- **During review**, `code-rules-check` checks a change for compliance with those same rules, and
  `docs-rules-check` does the same for your documents.
- **When authoring the rules**, `docs-rules-creator` helps the agent write the specifications that
  govern your documents.
- **When writing agent skills**, `skills-check` guides the agent through the Agent Skills specification and
  checks your skills against it with `lorecraft check skills`.

Install the skills with Vercel's [`skills`](https://github.com/vercel-labs/skills) CLI:

```sh
npx skills add https://github.com/lnsd/lorecraft/tree/main/skills
```

Or copy them into your agent's skills directory, such as `.claude/skills/` or `.agents/skills/`.

## Contributing

Read [CONTRIBUTING.md](https://github.com/lnsd/lorecraft/blob/main/CONTRIBUTING.md) before opening a pull request. Pull requests opened by autonomous
agents are closed without review.

## License

<sup>
Licensed under either of <a href="https://github.com/lnsd/lorecraft/blob/main/LICENSE-APACHE">Apache License, Version 2.0</a>
or <a href="https://github.com/lnsd/lorecraft/blob/main/LICENSE-MIT">MIT License</a>, at your option.
</sup>

<br>

<sub>
Unless you explicitly state otherwise, any contribution intentionally submitted
for inclusion in this project, as defined in the Apache-2.0 license, shall be
dual-licensed as above, without any additional terms or conditions.
</sub>
