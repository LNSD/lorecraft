---
name: "cli-version"
description: "lorecraft version: the one-line installed version, and with --verbose the commit, interpreter, platform and install path a bug report needs. Load when reporting a bug, or checking which lorecraft build is installed"
type: "feature"
status: "experimental"
components: "module:lorecraft.cli"
---

# `lorecraft version`

## Summary

`lorecraft version` prints the version of the installed package. With `--verbose` it adds what a
reproduction usually turns on: the git commit when running from a checkout, the Python interpreter, the
platform and where the package is installed. The version comes from the git tag the package was built from;
no file in the repository holds it.

## Table of Contents

1. [Key Concepts](#key-concepts)
2. [Configuration](#configuration)
3. [Usage](#usage)
4. [Limitations](#limitations)
5. [References](#references)
6. [Code References](#code-references)

## Key Concepts

- **Installed version**: The version recorded in the package metadata when it was built, derived from the
  nearest git tag; a build between tags carries a development suffix.
- **Checkout**: A git clone of lorecraft the package runs from, as with an editable install; an installed
  wheel has none.

## Configuration

| Argument or option | Default | Description |
|--------------------|---------|-------------|
| `--verbose`, `-v`  | off     | Add the commit, the interpreter, the platform and the install path |

## Usage

```bash
lorecraft version
lorecraft version --verbose
```

### Output

The short form is one line on stdout, the same line `lorecraft --version` prints:

```text
lorecraft 0.1.dev14+g376abe87a.d20260928
```

The verbose form adds one labelled line each:

```text
lorecraft 0.1.dev14+g376abe87a.d20260928
Commit:   0425125-dirty
Python:   3.13.14 (CPython)
Platform: Linux-6.18.49-1-MANJARO-x86_64-with-glibc2.44
Install:  /home/user/lorecraft/src/lorecraft
```

`Commit` is `git describe --tags --always --dirty` run in the checkout, so uncommitted work shows as `-dirty`.
The line is left out when the package does not run from a checkout of lorecraft, when git is missing,
or when the command fails or takes longer than five seconds.

### Exit Status

| Code | Meaning |
|------|---------|
| `0`  | The version was printed, with or without the commit line |
| `2`  | A usage error |

## Limitations

- The version line reflects the last build, not the working tree: after a new commit in a development
  install, only the `Commit` line moves until the package is rebuilt.

## References

- [cli](cli.md) - Base: the global `--version` option, which prints the short form

## Code References

- `src/lorecraft/cli/commands/version.py` - Declares the command
- `src/lorecraft/cli/version.py` - Builds both forms and runs the `git describe` probe
