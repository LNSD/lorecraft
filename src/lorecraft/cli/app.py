"""The root `lorecraft` application: global options, and nothing about any subcommand.

It declares options shared by every invocation and delegates commands to the registry.
"""

from dataclasses import dataclass
from typing import Annotated, Final

import typer

from .registry import mount
from .version import short_version


@dataclass(frozen=True, slots=True)
class GlobalOptions:
    """Options shared by every command in one invocation.

    Attributes:
        builtin_skills_schema: Whether the built-in Agent Skills schema is enabled.
    """

    builtin_skills_schema: bool


_HELP: Final[str] = "Check a repository's agent-facing documentation: rule documents, feature docs and skills."


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

    Args:
        value: Whether `--version` was passed. When false the callback does nothing and the run continues.

    Raises:
        typer.Exit: Always, when `value` is true. This is how Typer ends a successful run early.
    """
    if not value:
        return
    typer.echo(short_version())
    raise typer.Exit()


def _root(
    ctx: typer.Context,
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
    no_builtin_skills_schema: Annotated[
        bool,
        typer.Option('--no-builtin-skills-schema', help='Do not apply the built-in Agent Skills schema.'),
    ] = False,
) -> None:
    """Store global options for subcommands."""
    ctx.obj = GlobalOptions(builtin_skills_schema=not no_builtin_skills_schema)
