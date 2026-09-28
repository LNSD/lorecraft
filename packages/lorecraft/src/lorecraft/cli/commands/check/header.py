"""The `check header` command: validate documentation frontmatter.

This is the composition root of the header check: it establishes the root, snapshots it once, opens the
database over that snapshot, selects the documents against its model, hands them to ``run_header``, and prints
the run. Everything the check reads comes from the one snapshot, so the run sees a single moment of the tree
even while files change under it. Every ``Error`` escaping that flow is reported here and exits 2; a document
that cannot be decoded is a finding, not an error.
"""

import json
from pathlib import Path
from typing import Annotated, Literal

import typer

from lorecraft.checks import Database, HeaderRun, format_finding, run_header
from lorecraft.cli.root import find_root, resolve_root
from lorecraft.cli.select import select_document
from lorecraft_core.error import Error
from lorecraft_project.document import DocumentRef
from lorecraft_project.layout import SNAPSHOT_SCOPE
from lorecraft_vfs import take_snapshot

from . import app


class WorkingDirectoryError(Error):
    """The current working directory cannot be read, such as after it was deleted, so no root can be searched
    for from it.

    Attributes:
        detail: The operating system's reason.
    """

    detail: str

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(f'cannot read the current directory: {detail}')


@app.command(name='header')
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
        root_path = find_root(_working_directory()) if root is None else resolve_root(root)
        database = Database(take_snapshot(root_path, SNAPSHOT_SCOPE))
        model = database.model()
        refs: tuple[DocumentRef, ...]
        if paths:
            refs = tuple(select_document(model, root_path, argument) for argument in paths)
        else:
            refs = model.documents()
        run = run_header(database, refs)
    except Error as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    except OSError as exc:
        # The flow converts its own OSErrors into an Error where each is raised. What is left is Python 3.12:
        # its Path.is_dir re-raises every failure but a missing path, a PermissionError for one, from
        # find_root and resolve_root, where 3.13 and later answer False.
        typer.echo(f'cannot read input: {exc}', err=True)
        raise typer.Exit(code=2) from exc

    _print_run(run, output_format)
    if run.findings():
        raise typer.Exit(code=1)


def _working_directory() -> Path:
    """The current working directory, where the root search starts when no ``--root`` is given.

    Raises:
        WorkingDirectoryError: If the operating system cannot report it, such as after it was deleted.
    """
    try:
        return Path.cwd()
    except OSError as exc:
        raise WorkingDirectoryError(exc.strerror or str(exc)) from exc


def _print_run(run: HeaderRun, output_format: Literal['text', 'json']) -> None:
    """Print one run: the JSON report on stdout, or a line per ungoverned document and finding on stdout and
    the summary line on stderr, both in the run's report order."""
    reports = run.reports
    findings = run.findings()
    if output_format == 'json':
        report = {
            'checked': len(reports),
            'findings': [
                {
                    'file': str(finding.path),
                    'line': finding.line.value,
                    'rule': finding.rule,
                    'message': finding.message,
                }
                for finding in findings
            ],
            'ungoverned': [str(report.ref.path) for report in reports if not report.aspects],
        }
        typer.echo(json.dumps(report))
        return

    for report in reports:
        if not report.aspects:
            typer.echo(
                f'{report.ref.path}:1: [{report.ref.corpus}.ungoverned] '
                'no header schema for this corpus; frontmatter unvalidated'
            )
        for finding in report.result.findings:
            typer.echo(format_finding(finding))
    typer.echo(f'checked {len(reports)} file(s), {len(findings)} finding(s)', err=True)
