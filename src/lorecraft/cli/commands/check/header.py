"""The `check header` command: validate documentation frontmatter.

This is the composition root of the header check: it selects the documents of one snapshot, hands them to
``run_header``, and prints the run. Every ``Error`` escaping that flow is reported here and exits 2; a document
that cannot be decoded is a finding, not an error. The module also registers the check, so a bare
``lorecraft check`` runs it too.
"""

from pathlib import Path
from typing import Annotated, Final, Literal

import typer

from lorecraft.checks import run_header
from lorecraft.cli.check_run import DocumentCheck, print_run, register_check, select_documents
from lorecraft.core.error import Error

from . import app

HEADER_CHECK: Final[DocumentCheck] = register_check(
    DocumentCheck(
        name='header',
        run=run_header,
        ungoverned='no header schema for this corpus; frontmatter unvalidated',
    )
)


@app.command(name=HEADER_CHECK.name)
def header(
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
    """Check frontmatter against the target repository's schemas.

    Exit 0 when clean, 1 when findings exist, and 2 for invalid input or schemas.

    Raises:
        typer.Exit: With the documented status code for findings or invalid input.
    """
    try:
        database, refs = select_documents(root, paths)
        run = HEADER_CHECK.run(database, refs)
    except Error as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    except OSError as exc:
        # The flow converts its own OSErrors into an Error where each is raised. What is left is Python 3.12:
        # its Path.is_dir re-raises every failure but a missing path, a PermissionError for one, from
        # find_root and resolve_root, where 3.13 and later answer False.
        typer.echo(f'cannot read input: {exc}', err=True)
        raise typer.Exit(code=2) from exc

    print_run(run, output_format, HEADER_CHECK.ungoverned)
    if run.findings():
        raise typer.Exit(code=1)
