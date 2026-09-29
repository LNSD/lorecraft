"""The root `lorecraft` application: the global options, and nothing about any subcommand.

This module is closed to modification. It declares what is true of every invocation — the program
name, the help text, `--version` — and delegates the rest to the registry, so a new subcommand
never edits it.
"""

from typing import Annotated

import typer

from .registry import mount
from .version import short_version

_HELP: str = "Check a repository's agent-facing documentation: rule documents, feature docs and skills."


def build_app() -> typer.Typer:
    """Build the root application with every registered subcommand mounted on it.

    Returns:
        A fresh application. Each call discovers and mounts again, so a test can build one
        without inheriting state from another.
    """
    app = typer.Typer(
        name='lorecraft',
        help=_HELP,
        no_args_is_help=True,
        add_completion=False,
    )
    app.callback()(_root)
    mount(app)
    return app


def main() -> None:
    """Run the CLI. This is the `lorecraft` console script."""
    build_app()()


def _show_version(value: bool) -> None:
    """Print the short version and exit, when `--version` was passed.

    Eager option callbacks run before the subcommand is resolved, so this fires even when the
    rest of the command line is incomplete.

    Raises:
        typer.Exit: Always, when `value` is true. This is how Typer ends a successful run early.
    """
    if not value:
        return
    typer.echo(short_version())
    raise typer.Exit()


def _root(
    version: Annotated[
        bool,
        typer.Option(
            '--version',
            '-V',
            callback=_show_version,
            is_eager=True,
            help='Show the version and exit.',
        ),
    ] = False,
) -> None:
    """Root callback: it exists to carry the global options, and does nothing itself."""
