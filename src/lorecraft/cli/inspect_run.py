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
from lorecraft.project.workspace.model import BuiltinSpecLayer
from lorecraft.vfs import take_snapshot

from .failure import report_failure, report_first_load_failure
from .output import ExitStatus, OutputFormat
from .workspace_tree import render_json, render_text


def run_inspect(
    root: Path,
    output_format: OutputFormat,
    *,
    builtin_layers: tuple[BuiltinSpecLayer, ...],
) -> ExitStatus | None:
    """Print the workspace model of `root`; the body of `lorecraft inspect`.

    Args:
        root: The workspace root, already resolved by the command's argument.
        output_format: How to print the model, resolved from `--format` or its text default.
        builtin_layers: The builtin specification layers enabled for this inspection.

    Returns:
        `ExitStatus.FAILURE` when the scan or the load fails, which the command handler exits with; `None` when the
        model is printed.
    """
    try:
        # Under `docs/` the snapshot never reads through a symlink, so a linked `docs/` or `docs/__meta__/`
        # would draw a model with no corpora. `from_snapshot` refuses it instead of printing it as if the root declared
        # nothing.
        model = Database.from_snapshot(take_snapshot(root, SNAPSHOT_SCOPE), builtin_layers=builtin_layers).model()
        # Until a load failure is reported as one, a model that recorded one is no model to print.
        status = report_first_load_failure(model)
    except Error as exc:
        report_failure(exc)
        return ExitStatus.FAILURE
    if status is not None:
        return status

    match output_format:
        case OutputFormat.TEXT:
            typer.echo(render_text(root, model))
        case OutputFormat.JSON:
            typer.echo(render_json(root, model))
        case _:
            assert_never(output_format)
    return None
