"""The `inspect` subcommand: print the workspace model a root declares, as a tree or as JSON."""

from pathlib import Path
from typing import Annotated, assert_never

import typer

from lorecraft.checks import Database
from lorecraft.core.error import Error
from lorecraft.project.layout import SNAPSHOT_SCOPE
from lorecraft.vfs import take_snapshot

from ..failure import report_failure
from ..output import ExitStatus, OutputFormat
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
    output_format: Annotated[
        OutputFormat | None,
        typer.Option('--format', help='Output format: text or json. Defaults to text.'),
    ] = None,
    as_json: Annotated[
        bool,
        typer.Option('--json', hidden=True, help='Deprecated alias of --format json.'),
    ] = False,
) -> None:
    """Show the workspace model of a root: its corpora, specs and documents, and its agent skills.

    The root is scanned once and the model is loaded from that snapshot, so what is printed is one moment of
    the tree even while files change under it.

    Exit 0 when the model is printed, and 2 when the scan or the load fails or for invalid input.

    \f
    Raises:
        typer.BadParameter: If both `--format` and `--json` are given.
        typer.Exit: With code 2 when the scan or the load fails: an entry in scope that cannot be read or that
            changes kind while read, a skills directory that cannot be resolved or listed, a `docs/` or
            `docs/__meta__/` that is a symlink, or a structure specification that cannot be decoded or does not
            state usable rules.
    """
    # `--json` is kept so scripts written before `--format` keep working. `--format` defaults to `None` so a
    # given one can be told from an absent one, and giving both is refused rather than one silently winning.
    if as_json:
        if output_format is not None:
            raise typer.BadParameter(
                'give `--format json` alone; `--json` is its deprecated alias', param_hint="'--json'"
            )
        output_format = OutputFormat.JSON
    if output_format is None:
        output_format = OutputFormat.TEXT

    try:
        database = Database(take_snapshot(root, SNAPSHOT_SCOPE))
        # Under `docs/` the snapshot never reads through a symlink, so a linked `docs/` or `docs/__meta__/`
        # would draw a model with no corpora. Refused instead of printed as if the root declared nothing.
        database.reject_linked_layout()
        model = database.model()
    except Error as exc:
        report_failure(exc)
        raise typer.Exit(code=ExitStatus.FAILURE) from exc

    match output_format:
        case OutputFormat.TEXT:
            typer.echo(render_text(root, model))
        case OutputFormat.JSON:
            typer.echo(render_json(root, model))
        case _:
            assert_never(output_format)
