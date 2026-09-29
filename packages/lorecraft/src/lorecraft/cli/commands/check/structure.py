"""The `check structure` command: validate the section structure of documentation.

This is the composition root of the structure check: it selects the documents of one snapshot, hands them to
``run_structure``, and prints the run. Every ``Error`` escaping that flow is reported here and exits 2; a
document that cannot be decoded is a finding, not an error. The module also registers the check, so a bare
``lorecraft check`` runs it too.
"""

from pathlib import Path
from typing import Annotated, Final, Literal

import typer

from lorecraft.checks import run_structure
from lorecraft.cli.check_run import DocumentCheck, print_run, register_check, select_documents
from lorecraft_core.error import Error

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
        Literal['text', 'json'],
        typer.Option('--format', help='Output format: text or json.'),
    ] = 'text',
) -> None:
    """Check section structure against the target repository's structure specifications.

    Exit 0 when clean, 1 when findings exist, and 2 for invalid input or specifications.

    Raises:
        typer.Exit: With the documented status code for findings or invalid input.
    """
    try:
        database, refs = select_documents(root, paths)
        run = STRUCTURE_CHECK.run(database, refs)
    except Error as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    except OSError as exc:
        # As in `check header`: what is left is Python 3.12's Path.is_dir, which re-raises a PermissionError
        # from find_root and resolve_root where 3.13 and later answer False.
        typer.echo(f'cannot read input: {exc}', err=True)
        raise typer.Exit(code=2) from exc

    print_run(run, output_format, STRUCTURE_CHECK.ungoverned)
    if run.findings():
        raise typer.Exit(code=1)
