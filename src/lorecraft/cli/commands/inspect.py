"""The `inspect` subcommand: print the workspace model a root declares, as a tree or as JSON.

The command declares the arguments and the help text; the flow is in `inspect_run`, which this module imports only
when the command runs, so that `--help` and `--version` never import the workspace model.
"""

from pathlib import Path
from typing import Annotated

import typer

from ..output import OutputFormat
from ..registry import register


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
    # Imported here, not at the top: `inspect_run` imports the workspace model, which `--help` never uses.
    from ..inspect_run import run_inspect

    status = run_inspect(root, _resolve_format(output_format, as_json=as_json))
    if status is not None:
        raise typer.Exit(code=status)


def _resolve_format(output_format: OutputFormat | None, *, as_json: bool) -> OutputFormat:
    """The format the model is printed in, once the deprecated `--json` alias is read as `--format json`.

    `--json` is kept so scripts written before `--format` keep working. `--format` defaults to `None` so a given one
    can be told from an absent one, and giving both is refused rather than one silently winning.

    Args:
        output_format: The `--format` option; `None` when it was not given.
        as_json: Whether the deprecated `--json` alias was given.

    Raises:
        typer.BadParameter: If both `--format` and `--json` are given.
    """
    if as_json:
        if output_format is not None:
            raise typer.BadParameter(
                'give `--format json` alone; `--json` is its deprecated alias', param_hint="'--json'"
            )
        return OutputFormat.JSON
    if output_format is None:
        return OutputFormat.TEXT
    return output_format
