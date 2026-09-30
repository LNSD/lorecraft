"""The `check frontmatter` command: validate documentation frontmatter.

This is the composition root of the frontmatter check: it selects the documents of one snapshot, hands them to
``run_frontmatter``, and prints the run. Every ``Error`` escaping that flow is reported here and exits 2; a document
that cannot be decoded is a finding, not an error. The module also registers the check, so a bare
``lorecraft check`` runs it too.

``check header`` is kept as a hidden alias of the command: the check's name from when the frontmatter schema had a
``<stem>.header.json`` file of its own. It is the same handler under a second name, not a second check, so a bare
``lorecraft check`` still runs the frontmatter check once.
"""

from pathlib import Path
from typing import Annotated, Final, Literal

import typer

from lorecraft.checks import run_frontmatter
from lorecraft.cli.check_run import DocumentCheck, print_run, register_check, select_documents
from lorecraft.cli.failure import report_failure
from lorecraft.core.error import Error

from . import app

FRONTMATTER_CHECK: Final[DocumentCheck] = register_check(
    DocumentCheck(
        name='frontmatter',
        run=run_frontmatter,
        ungoverned='no frontmatter schema for this corpus; frontmatter unvalidated',
    )
)

_HEADER_ALIAS: Final[str] = 'header'
"""The check's former name, still accepted on the command line and hidden from ``--help``."""


@app.command(name=FRONTMATTER_CHECK.name)
def frontmatter(
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
    """Check frontmatter against the `frontmatter` schemas in the target repository's structure specifications.

    Exit 0 when clean, 1 when findings exist, and 2 for invalid input or schemas.

    Raises:
        typer.Exit: With the documented status code for findings or invalid input.
    """
    try:
        database, refs = select_documents(root, paths)
        run = FRONTMATTER_CHECK.run(database, refs)
    except Error as exc:
        report_failure(exc)
        raise typer.Exit(code=2) from exc

    print_run(run, output_format, FRONTMATTER_CHECK.ungoverned)
    if run.findings():
        raise typer.Exit(code=1)


# The alias is the same function registered under a second name. Typer's decorator returns the function unchanged, so
# calling it here, rather than stacking it on the definition, keeps the one command's definition in one place.
app.command(name=_HEADER_ALIAS, hidden=True)(frontmatter)
