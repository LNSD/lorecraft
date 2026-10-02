---
name: "python-typer"
description: "Command-line commands with Typer: Annotated parameters described in help=, the docstring as --help cut at a form-feed line, a group's options refused before a named subcommand, hidden aliases, eager global flags, handlers that map arguments and exit, and CliRunner tests in a plain terminal. Load when adding or changing a command, a command group, an option or an argument, editing a command's docstring, or testing what a command prints"
type: "core"
scope: "pkg:pypi/typer"
---

# Typer Commands

**Everything a user reads about a command comes from its declaration**: the signature is its arguments and
options, the docstring is its `--help`, and the body maps what was typed onto the library and exits. How a
command joins the command line is owned by [pattern-registry](pattern-registry.md). The framework exception a
command exits with is owned by [error-boundaries](error-boundaries.md), and reporting a failure before exiting
by [error-handling](error-handling.md). This document is about declaring a command with Typer.

## 1. Every Parameter Is `Annotated`, With Its Own `help=`

A command parameter is `Annotated[T, typer.Option(...)]` or `Annotated[T, typer.Argument(...)]`, its default
the Python default after `=`. An option's name is spelled out, `'--json'` for a parameter named `as_json`, so
renaming the Python parameter never renames the option. `help=` is a sentence ending in a period, and where
the default is `None`, which `--help` cannot show, it says what an absent value means: "Defaults to the
nearest parent containing docs/__meta__." A fixed set of values is an `Enum` whose values are what the option
accepts; Typer lists them in `--help` and refuses any other.

The docstring carries no `Args:`. Typer prints each `help=` beside its parameter, which is where the reader of
a command looks, and an `Args:` line would be a second description that nothing keeps in step.

```python
# ❌ Bad — `--help` listed `--as-json / --no-as-json` with no description; the Args: lines reached no user
@register('outline')
def outline(document: Path, as_json: bool = False) -> None:
    """Print a document's section outline.

    Args:
        document: Document to read.
        as_json: Print JSON.
    """
```

```python
# ✅ Good — each parameter's description sits beside it, and `--help` prints every word of it
@register('outline')
def outline(
    document: Annotated[Path, typer.Argument(help='Markdown document whose outline is printed.')],
    as_json: Annotated[
        bool,
        typer.Option('--json', help='Print the outline as JSON instead of drawing it.'),
    ] = False,
) -> None:
    """Print a document's section outline."""
```

## 2. The Docstring Is the `--help`, Cut at a `\f` Line

Typer prints a command's docstring as its `--help`, and the summary line as the command's entry in its
parent's list. It stops at a form feed, so a docstring with a section for code readers, `Raises:`, puts a line
holding only `\f` before it. Above the cut is the user's: what the command does and the statuses it exits
with. Below it is the code reader's, written as [python-docstrings](python-docstrings.md) says. A docstring
with no section needs no cut. A group callback's docstring is written the same way.

The docstring stays non-raw: in `r"""…"""` the `\f` is a backslash and an `f`, which Typer prints. Ruff's
`D301` asks for a raw docstring wherever a backslash appears, so `pyproject.toml` ignores it under
`src/lorecraft/cli/commands/`, with the reason beside the entry.

An application's own help, the root's or a group's, is the `help=` of its `typer.Typer`, which Typer prefers
to a callback's docstring.

```python
# ❌ Bad — no cut: `lorecraft outline --help` printed the Raises section, exception names and all
def outline(document: Path) -> None:
    """Print a document's section outline.

    Raises:
        typer.Exit: With code 1 when the document cannot be read.
    """
```

```python
# ✅ Good — the user reads the summary and the exit statuses; the code reader reads on past the cut
def outline(document: Path) -> None:
    """Print a document's section outline.

    Exit 0 when printed, and 1 when the document cannot be read.

    \f
    Raises:
        typer.Exit: With code 1 when the document cannot be read.
    """
```

## 3. A Group's Option Belongs to the Run It Starts

A group that runs on its own, `invoke_without_command=True`, may take options for that run, and each
subcommand declares its own. Typer parses the group's options before the subcommand's name and hands the
subcommand none of them, so the group's options default to `None`, which tells a given option from an absent
one, and its callback refuses one given before a subcommand's name with `typer.BadParameter`. That exits as a
usage error naming where the option goes. Read and dropped instead, `lorecraft check --root . frontmatter`
would have checked the repository around the working directory.

```python
# ✅ Good — the option is the bare run's; before a subcommand it is refused, not silently dropped
@app.callback()
def lint_all(
    context: typer.Context,
    root: Annotated[Path | None, typer.Option('--root', help='Repository root.')] = None,
) -> None:
    """Run every lint when no lint is named.

    \f
    Raises:
        typer.BadParameter: If `--root` is given before a named lint, which takes its own.
    """
    if context.invoked_subcommand is not None:
        if root is not None:
            raise typer.BadParameter(
                f'give it after the lint name, as `lorecraft lint {context.invoked_subcommand} --root ...`',
                param_hint="'--root'",
            )
        return
```

## 4. A Second Name Is the Same Function, Registered Hidden

A command kept under a former name is the same function registered again under that name with `hidden=True`.
The registration is a call after the definition rather than a second decorator stacked on it, so the command
is defined in one place. `--help` lists the current name alone, and the former one keeps working. A wrapper
forwarding to the command would be a second signature to keep in step with the first.

```python
# ✅ Good — one definition, two names; only `outline` appears in `--help`
@app.command(name='outline')
def outline(document: Path) -> None:
    """Print a document's section outline."""


app.command(name='headings', hidden=True)(outline)
```

## 5. A Global Flag Is an Eager Option on the Root Callback

An option true of every invocation is declared on the root application's callback, with `is_eager=True` and a
`callback=` that does the work and raises `typer.Exit()`. An eager option runs before Typer resolves the
subcommand, so it answers even when the rest of the line is incomplete. The root callback does nothing else.

The root application is built with `no_args_is_help=True`, so a bare invocation prints the help and exits as a
usage error rather than doing nothing, and with `add_completion=False`, so `--help` lists no shell-completion
options.

```python
# ✅ Good — the flag answers before any subcommand is looked up, then ends the run
def _list_agents(value: bool) -> None:
    if not value:
        return
    typer.echo(render_agents(known_agents()))
    raise typer.Exit()


def _root(
    agents: Annotated[
        bool,
        typer.Option('--agents', callback=_list_agents, is_eager=True, help='List the known agents and exit.'),
    ] = False,
) -> None:
    """Carry the global options; the root does nothing itself."""
```

## 6. A Handler Maps Arguments, Calls the Library, and Exits

A command's body maps its arguments onto the library, calls it, and writes what comes back with `typer.echo`:
the result on stdout, a summary or an error with `err=True`, so a reader parsing stdout reads the result
alone. A clean run returns; any other outcome raises `typer.Exit(code=...)` with the status the command
documents. Nothing in `src/lorecraft/` outside `cli/` imports `typer`: a library that raised Typer's
exceptions would be tied to the command line.

```python
# ❌ Bad — the summary went to stdout, inside the JSON, and every script parsing `--json` failed on it
typer.echo(render_outline(report, as_json=as_json))
typer.echo(f'{len(report.problems)} problem(s)')
```

```python
# ✅ Good — the result on stdout, the summary on stderr, and the status through Typer
typer.echo(render_outline(report, as_json=as_json))
typer.echo(f'{len(report.problems)} problem(s)', err=True)
if report.problems:
    raise typer.Exit(code=1)
```

## 7. A Command Is Tested Through `CliRunner`, Its Help in a Plain Terminal

A command is tested by invoking an application built for the test through Typer's `CliRunner`, which runs it
in process and captures its output and exit status; the tier that test belongs to is owned by
[test-organization](test-organization.md). A test of `--help` passes a plain terminal in `env=`: Rich draws
the help for the terminal it finds, so colour codes and the wrap width otherwise change from one machine to
the next, and the reviewed snapshot fails on CI alone.

```python
# ✅ Good — a dumb terminal 80 columns wide draws the same help on every machine
PLAIN_TERMINAL: Final[dict[str, str | None]] = {'TERM': 'dumb', 'COLUMNS': '80'}


def test_outline_with_help_prints_the_description_and_stops_before_raises(self, snapshot: SnapshotAssertion) -> None:
    #: Given
    app = build_app()

    #: When
    result = runner.invoke(app, ['outline', '--help'], env=PLAIN_TERMINAL)

    #: Then
    assert result.exit_code == 0, result.output
    assert result.stdout == snapshot, 'the outline help matches the reviewed snapshot'
```

## Checklist

Before committing code, verify:

- [ ] Every command parameter is `Annotated` with `typer.Option` or `typer.Argument`, its option name spelled
      out, and a `help=` sentence saying what an absent `None` means
- [ ] No command docstring has `Args:`, and a fixed set of values is an `Enum` the option accepts
- [ ] A command or group callback docstring with a section has a `\f` line before it, and is not raw
- [ ] The prose above the cut says what the command does and the statuses it exits with
- [ ] A root or group application states its help in `typer.Typer(help=...)`
- [ ] A group's own options default to `None`, and are refused with `typer.BadParameter` before a subcommand
- [ ] A former name is the same function registered with `hidden=True`, never a wrapper
- [ ] A global flag is an eager option on the root callback, whose callback raises `typer.Exit()`
- [ ] A handler writes with `typer.echo`, a summary or an error with `err=True`, and returns when clean or
      raises `typer.Exit(code=...)`
- [ ] Nothing in `src/lorecraft/` outside `cli/` imports `typer`
- [ ] A command test invokes a built application through `CliRunner`, and a `--help` test passes a plain
      terminal

## References

- [python-docstrings](python-docstrings.md) - Related: Owns the sections below the cut, `Raises:` included
- [pattern-registry](pattern-registry.md) - Related: Owns how a command or a group joins the command line
- [error-boundaries](error-boundaries.md) - Related: Owns why `typer.BadParameter` and `typer.Exit` are raised
  only in a command
- [error-handling](error-handling.md) - Related: Owns catching `Error` at the command line's top level to
  report it and exit
- [test-organization](test-organization.md) - Related: Owns the tier a `CliRunner` test belongs to
- [principle-validate-at-edge](principle-validate-at-edge.md) - Foundation: A command is the edge where input
  is refused as a usage error

## External References

- [Typer — Command help](https://typer.tiangolo.com/tutorial/commands/help/)
- [Typer — Testing](https://typer.tiangolo.com/tutorial/testing/)
- [Click — Truncating help texts](https://click.palletsprojects.com/en/stable/documentation/#truncating-help-texts)
