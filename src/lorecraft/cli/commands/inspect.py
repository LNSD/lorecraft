"""The `inspect` subcommand: print the workspace model a root declares, as a tree or as JSON."""

from pathlib import Path
from typing import Annotated

import typer

from lorecraft.checks import Database
from lorecraft.core.error import Error
from lorecraft.project.layout import SNAPSHOT_SCOPE
from lorecraft.vfs import take_snapshot

from ..failure import report_failure
from ..registry import register
from ..workspace_tree import render_json, render_text


@register('inspect')
def inspect(
    root: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=False,
            resolve_path=True,
            help='Workspace root to inspect. Defaults to the current directory.',
        ),
    ] = Path('.'),
    as_json: Annotated[
        bool,
        typer.Option('--json', help='Print the model as JSON instead of drawing it.'),
    ] = False,
) -> None:
    """Show the workspace model of a root: its corpora, specs and documents, and its agent skills.

    The root is scanned once and the model is loaded from that snapshot, so what is printed is one moment of
    the tree even while files change under it.

    Raises:
        typer.Exit: With code 1 when the scan or the load fails: an entry in scope that cannot be read, a
            skills directory that cannot be resolved or listed, a ``docs/`` or ``docs/__meta__/`` that is a
            symlink, or a structure specification that cannot be decoded or does not state usable rules.
    """
    try:
        database = Database(take_snapshot(root, SNAPSHOT_SCOPE))
        # Under `docs/` the snapshot never reads through a symlink, so a linked `docs/` or `docs/__meta__/`
        # would draw a model with no corpora. Refused instead of printed as if the root declared nothing.
        database.require_real_layout()
        model = database.model()
    except Error as exc:
        report_failure(exc)
        raise typer.Exit(code=1) from exc

    if as_json:
        typer.echo(render_json(root, model))
        return
    typer.echo(render_text(root, model))
