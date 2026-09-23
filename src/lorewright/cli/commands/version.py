"""The `version` subcommand: report the installed version, briefly or in full."""

from typing import Annotated

import typer

from .._registry import register
from .._version import detailed_version, git_description, short_version


@register('version')
def version(
    verbose: Annotated[
        bool,
        typer.Option('--verbose', '-v', help='Include the commit, the interpreter, the platform and the install path.'),
    ] = False,
) -> None:
    """Show the installed version."""
    if not verbose:
        typer.echo(short_version())
        return
    typer.echo(detailed_version(git_description()))
