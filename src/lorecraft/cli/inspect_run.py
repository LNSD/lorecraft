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

from .failure import exit_on_load_failure, report_failure
from .output import ExitStatus, OutputFormat
from .workspace_tree import render_json, render_text


def run_inspect(root: Path, output_format: OutputFormat) -> None:
    """Print the workspace model of `root`; the body of `lorecraft inspect`.

    Args:
        root: The workspace root, already resolved by the command's argument.
        output_format: How to print the model, already resolved from `--format` and the `--json` alias.

    Raises:
        typer.Exit: With code 2 when the scan or the load fails.
    """
    try:
        # Under `docs/` the snapshot never reads through a symlink, so a linked `docs/` or `docs/__meta__/`
        # would draw a model with no corpora. `open` refuses it instead of printing it as if the root declared
        # nothing.
        model = Database.open(take_snapshot(root, SNAPSHOT_SCOPE)).model()
        # Until a load failure is reported as one, a model that recorded one is no model to print.
        exit_on_load_failure(model)
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
