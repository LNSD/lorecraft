---
name: "cli"
description: "The lorecraft command line as a whole: its global options, how commands are named and found, and what every command shares, such as the exit status of a usage error. Load when running lorecraft for the first time, or looking for the command that does something"
type: "meta"
status: "experimental"
components: "module:lorecraft.cli"
---

# The `lorecraft` Command Line

## Summary

`lorecraft` is the console script the `lorecraft` package installs, with `lc` as a shorter name for it. It checks a repository's agent-facing
documentation against the specifications that repository declares under `docs/__meta__/`, and shows what those
specifications govern. The application itself only routes: each command is its own subcommand, and a bare
`lorecraft` prints its help on stdout and exits `2`.

## Table of Contents

1. [Key Concepts](#key-concepts)
2. [Architecture](#architecture)
3. [Configuration](#configuration)
4. [Limitations](#limitations)
5. [References](#references)

## Key Concepts

- **Command**: One subcommand a user types, such as `lorecraft inspect`; each has its own help and options.
- **Command group**: A command that holds subcommands of its own, such as `lorecraft check`.
- **Global option**: An option of `lorecraft` itself, given before any command name.
- **Repository root**: The directory whose `docs/__meta__/` a command reads; each command that reads one says
  how it finds it.

## Architecture

### Invoking the Command

Run `lorecraft` directly when it is on `PATH`. For an on-demand run, use `uv tool run lorecraft` (or its alias
`uvx lorecraft`). In a Python project that declares Lorecraft as a dependency, `uv run lorecraft` runs the
command from that project's environment.

### Finding a Command

`lorecraft --help` lists the commands, and `lorecraft <command> --help` lists a command's options and, for a
group, its subcommands. The help is the inventory: no document lists the commands, so none goes stale when
one is added.

### What Every Command Shares

- Every command and group takes `--help`.
- A command line the parser rejects — an unknown command or option, a missing or malformed value — prints the
  usage and the error on stderr and exits `2`, before the command runs.
- No command reads an environment variable or a configuration file: what a command does is decided by its
  command line and by the repository it reads.
- Output a reader can script against goes to stdout; summaries and errors go to stderr.
- A failure that stops a command is printed as `error: <message>`, then one indented `caused by: <message>` line
  for each failure beneath it: what the command was doing first, then each step inside it that failed, down to
  the one where the failure began.

## Configuration

| Argument or option | Default | Description |
|--------------------|---------|-------------|
| `--version`, `-V`  | off     | Print `lorecraft <version>` and exit `0`, whatever command or arguments follow it; an unknown option of `lorecraft` itself, as in `-V --bogus`, is still a usage error |

The version printed is the one the installed package was built with, the same line `lorecraft version` prints.

## Limitations

- Shell completion is not installed: `lorecraft` offers no `--install-completion`.

## References

- [spec](spec.md) - Related: the specification files the commands read
