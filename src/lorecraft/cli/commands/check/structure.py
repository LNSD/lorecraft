"""The `check structure` command: validate the section structure of documentation.

This is the composition root of the structure check: it selects the documents of one snapshot, hands them to
``run_structure``, and prints the run. Every ``Error`` escaping that flow is reported here and exits 2; a
document that cannot be decoded is a finding, not an error. The module also registers the check, so a bare
``lorecraft check`` runs it too.
"""

from pathlib import Path
from typing import Annotated, Final

import typer

from lorecraft.checks import run_structure
from lorecraft.cli.check_run import CheckExit, DocumentCheck, OutputFormat, print_run, register_check, select_documents
from lorecraft.cli.failure import report_failure
from lorecraft.core.error import Error

from . import app

STRUCTURE_CHECK: Final[DocumentCheck] = register_check(
    DocumentCheck(
        name='structure',
        run=run_structure,
        ungoverned='no structure spec for this corpus; structure unvalidated',
    )
)


@app.command(name=STRUCTURE_CHECK.name)
def structure(
    paths: Annotated[
        list[Path] | None,
        typer.Argument(
            help=(
                'Markdown files to check, relative to the current directory. '
                'Defaults to every Markdown file directly inside a corpus directory under ROOT/docs.'
            )
        ),
    ] = None,
    root: Annotated[
        Path | None,
        typer.Option('--root', help='Repository root. Defaults to the nearest parent containing docs/__meta__.'),
    ] = None,
    output_format: Annotated[
        OutputFormat,
        typer.Option('--format', help='Output format: text or json.'),
    ] = OutputFormat.TEXT,
) -> None:
    """Check section structure against the target repository's structure specifications.

    Exit 0 when clean, 1 when findings exist, and 2 for invalid input or specifications.

    \f
    Raises:
        typer.Exit: With the documented status code for findings or invalid input.
    """
    try:
        database, refs = select_documents(root, paths)
        run = STRUCTURE_CHECK.run(database, refs)
    except Error as exc:
        report_failure(exc)
        raise typer.Exit(code=CheckExit.FAILURE) from exc

    print_run(run, output_format, STRUCTURE_CHECK.ungoverned)
    if run.findings():
        raise typer.Exit(code=CheckExit.FINDINGS)
