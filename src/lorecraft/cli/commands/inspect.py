"""The `inspect` subcommand: print the workspace model a root declares, as a tree or as JSON."""

from pathlib import Path
from typing import Annotated

import typer

from lorecraft.core.error import Error
from lorecraft.project.layout import SNAPSHOT_SCOPE
from lorecraft.project.workspace import load_model
from lorecraft.vfs import VirtualFileSystem, take_snapshot

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
            skills directory that cannot be resolved or listed, or a structure specification that cannot be
            decoded or does not state usable rules.
    """
    try:
        snapshot = take_snapshot(root, SNAPSHOT_SCOPE)
        model = load_model(VirtualFileSystem(snapshot))
    except Error as exc:
        typer.echo(f'error: {exc}', err=True)
        raise typer.Exit(code=1) from exc

    if as_json:
        typer.echo(render_json(root, model))
        return
    typer.echo(render_text(root, model))
