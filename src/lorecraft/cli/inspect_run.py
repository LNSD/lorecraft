"""The flow behind `lorecraft inspect`: scan a root once, load the workspace model from that snapshot, and print it.

It lives apart from `commands/inspect.py` so that importing the command, which `--help` and `--version` do, does not
import the workspace model: the command imports this module only when it runs.
"""

from pathlib import Path
from typing import assert_never

import typer

from lorecraft.core.error import Error
from lorecraft.project.database import Database
from lorecraft.project.layout import SNAPSHOT_SCOPE
from lorecraft.vfs import take_snapshot

from .failure import report_failure
from .output import ExitStatus, OutputFormat
from .workspace_tree import render_json, render_text


def run_inspect(root: Path, output_format: OutputFormat | None, as_json: bool) -> None:
    """Print the workspace model of `root`; the body of `lorecraft inspect`.

    Args:
        root: The workspace root, already resolved by the command's argument.
        output_format: The `--format` option; `None` when it was not given.
        as_json: Whether the deprecated `--json` alias was given.

    Raises:
        typer.BadParameter: If both `--format` and `--json` are given.
        typer.Exit: With code 2 when the scan or the load fails.
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
