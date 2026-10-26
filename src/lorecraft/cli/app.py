"""The root `lorecraft` application: global options, and nothing about any subcommand.

It declares options shared by every invocation and delegates commands to the registry.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated, Final

import typer

from .registry import mount
from .version import short_version

if TYPE_CHECKING:
    from lorecraft.project.workspace.model import BuiltinSpecLayer


@dataclass(frozen=True, slots=True)
class GlobalOptions:
    """Options shared by every command in one invocation.

    Attributes:
        builtin_layers: The builtin specification layers enabled for this invocation.
    """

    builtin_layers: tuple[BuiltinSpecLayer, ...]


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


def global_options(ctx: typer.Context) -> GlobalOptions:
    """Return the options stored by the root callback.

    Args:
        ctx: A command context in this application.

    Raises:
        AssertionError: If the root callback did not store its options.
    """
    options = ctx.find_root().obj
    assert isinstance(options, GlobalOptions), 'the root callback stores global options'
    return options


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
    no_agent_skills_spec: Annotated[
        bool,
        typer.Option(
            '--no-agent-skills-spec',
            help='Do not apply the builtin Agent Skills specification and skill floor.',
        ),
    ] = False,
    no_builtin_skills_schema: Annotated[
        bool,
        typer.Option(
            '--no-builtin-skills-schema',
            hidden=True,
            help='Deprecated alias for --no-agent-skills-spec.',
        ),
    ] = False,
) -> None:
    """Store global options for subcommands."""
    if no_agent_skills_spec and no_builtin_skills_schema:
        raise typer.BadParameter('give only one of --no-agent-skills-spec and --no-builtin-skills-schema')
    # Keep project imports out of --version and --help startup paths.
    from lorecraft.project.workspace.builtin import AGENT_SKILLS_SPEC_LAYER

    builtin_layers = () if no_agent_skills_spec or no_builtin_skills_schema else (AGENT_SKILLS_SPEC_LAYER,)
    ctx.obj = GlobalOptions(builtin_layers=builtin_layers)
