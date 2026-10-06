"""The `check` command: run every enabled rule over the whole workspace, and report what the rules found.

This is the composition root of the rules engine. It establishes the root, takes one snapshot, opens the database
over it, selects every subject of the workspace, builds the rule table from the package's rules, and hands all three
to the runner; what comes back is rendered by `diagnostics` and decides the exit code. Every `Error` escaping that
flow is reported here and exits 2; a file that does not decode is a diagnostic, not an error.
"""

from pathlib import Path
from typing import Annotated, assert_never

import typer

from lorecraft import rules
from lorecraft.checks import RuleTable, SubjectReport, check_subjects
from lorecraft.core.error import Error
from lorecraft.project.database import Database
from lorecraft.project.layout import SNAPSHOT_SCOPE
from lorecraft.rules.declaration import Severity
from lorecraft.rules.registry import Registry
from lorecraft.vfs import take_snapshot

from ..diagnostics import render_coverage, render_diagnostics, render_json, render_summary
from ..failure import report_failure
from ..output import ExitStatus, OutputFormat
from ..registry import register
from ..root import establish_root
from ..subjects import select_workspace


@register('check')
def check(
    root: Annotated[
        Path | None,
        typer.Option('--root', help='Repository root. Defaults to the nearest parent containing docs/__meta__.'),
    ] = None,
    output_format: Annotated[
        OutputFormat,
        typer.Option('--format', help='Output format: text or json.'),
    ] = OutputFormat.TEXT,
) -> None:
    """Check every document and skill of the workspace: frontmatter, outline, length, links and layout.

    As text, the diagnostics go to stdout, and the ungoverned subjects and a summary to stderr.

    As JSON, one document goes to stdout.

    Exit 0 when no diagnostic is an error, 1 when any is, and 2 for invalid input or specifications.

    \f
    Raises:
        typer.Exit: With the documented status code for an error diagnostic or invalid input.
    """
    try:
        database = Database(take_snapshot(establish_root(root), SNAPSHOT_SCOPE))
        # Root discovery follows symlinks and the snapshot, under `docs/`, does not, so a linked `docs/__meta__/`
        # passes the first and is empty in the second. Refused here, before a run over no documents can report
        # success.
        database.reject_linked_layout()
        subjects = select_workspace(database)
        table = RuleTable.from_registry(Registry.load(rules))
        reports = check_subjects(database, subjects, table)
    except Error as exc:
        report_failure(exc)
        raise typer.Exit(code=ExitStatus.FAILURE) from exc

    match output_format:
        case OutputFormat.TEXT:
            _print_text(reports)
        case OutputFormat.JSON:
            typer.echo(render_json(reports))
        case _:
            assert_never(output_format)
    if _has_error(reports):
        raise typer.Exit(code=ExitStatus.FINDINGS)


def _print_text(reports: tuple[SubjectReport, ...]) -> None:
    """Print the diagnostics on stdout, then the coverage and the summary on stderr, each only when it holds a line.

    Args:
        reports: One report per subject the run checked.
    """
    diagnostics = render_diagnostics(reports)
    if diagnostics:
        typer.echo(diagnostics)
    coverage = render_coverage(reports)
    if coverage:
        typer.echo(coverage, err=True)
    typer.echo(render_summary(reports), err=True)


def _has_error(reports: tuple[SubjectReport, ...]) -> bool:
    """True when any diagnostic of any report is an error; warnings alone let a run pass.

    Args:
        reports: One report per subject the run checked.
    """
    for report in reports:
        for diagnostic in report.diagnostics:
            if diagnostic.severity is Severity.ERROR:
                return True
    return False
