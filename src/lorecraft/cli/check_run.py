"""The flow behind `lorecraft check`: run every enabled rule over the whole workspace, and report what the rules found.

This is the composition root of the rules engine. It loads the package's rules and parses `--select` and `--ignore`
against them, establishes the root, takes one snapshot, opens the database over it, selects every subject of the
workspace, builds the rule table from the rules and the selection, and hands the database, the subjects and the
table to the runner; what comes back is rendered by `diagnostics` and decides the exit code. Every `Error` escaping
that flow is reported here and exits 2; a file that does not decode is a diagnostic, not an error. A selection that
holds an alias code, or names a rule its level leaves off, is warned of on stderr, and the run goes on.

It lives apart from `commands/check.py` so that importing the command, which `--help` and `--version` do, does not
import the rules engine: the command imports this module only when it runs.
"""

from pathlib import Path
from typing import assert_never

import typer

from lorecraft import rules
from lorecraft.checks import RuleTable, SubjectReport, check_subjects, selected_rules_left_off
from lorecraft.core.error import Error
from lorecraft.project.database import Database
from lorecraft.project.layout import SNAPSHOT_SCOPE
from lorecraft.rules.declaration import Severity
from lorecraft.rules.registry import Registry
from lorecraft.vfs import take_snapshot

from .diagnostic_text import render_text
from .diagnostics import render_coverage, render_json, render_prefix_summary, render_short, render_summary
from .failure import report_failure
from .output import ColorChoice, DiagnosticFormat, ExitStatus
from .root import establish_root
from .rule_selection import parse_rule_selection, print_selection_warnings
from .sources import read_sources
from .subjects import select_workspace
from .terminal import detect_text_style, read_color_environment


def run_check(
    root: Path | None,
    output_format: DiagnosticFormat,
    color: ColorChoice,
    select: list[str] | None,
    ignore: list[str] | None,
) -> None:
    """Run the rules over the workspace and write the report; the body of `lorecraft check`.

    Args:
        root: The `--root` option; `None` searches upward from the working directory.
        output_format: How the diagnostics are written.
        color: When to emphasise the text format with colour.
        select: The `--select` selectors, as given.
        ignore: The `--ignore` selectors, as given.

    Raises:
        typer.Exit: With the documented status code for an error diagnostic or invalid input.
    """
    try:
        registry = Registry.load(rules)
        parsed = parse_rule_selection(registry, select=select, ignore=ignore)
        print_selection_warnings(parsed, selected_rules_left_off(registry, parsed.selection))
        database = Database(take_snapshot(establish_root(root), SNAPSHOT_SCOPE))
        # Root discovery follows symlinks and the snapshot, under `docs/`, does not, so a linked `docs/__meta__/`
        # passes the first and is empty in the second. Refused here, before a run over no documents can report
        # success.
        database.reject_linked_layout()
        subjects = select_workspace(database)
        table = RuleTable.from_registry(registry, parsed.selection)
        reports = check_subjects(database, subjects, table)
    except Error as exc:
        report_failure(exc)
        raise typer.Exit(code=ExitStatus.FAILURE) from exc

    match output_format:
        case DiagnosticFormat.TEXT:
            _print_text(reports, database, color)
        case DiagnosticFormat.SHORT:
            _print_short(reports)
        case DiagnosticFormat.JSON:
            typer.echo(render_json(reports))
        case _:
            assert_never(output_format)
    if _has_error(reports):
        raise typer.Exit(code=ExitStatus.FINDINGS)


def _print_text(reports: tuple[SubjectReport, ...], database: Database, color: ColorChoice) -> None:
    """Draw the diagnostics on stdout, then the coverage and the summaries on stderr, each only when it holds a line.

    Args:
        reports: One report per subject the run checked.
        database: The revision the run checked, which the source lines are excerpted from.
        color: When to emphasise the diagnostics with colour.
    """
    style = detect_text_style(color, read_color_environment())
    diagnostics = render_text(reports, read_sources(database, reports), style)
    if diagnostics:
        # Click strips colour from a stream that is not a terminal unless told not to; `style` already decided.
        typer.echo(diagnostics, color=style.color)
    _print_stderr(reports, with_prefixes=True)


def _print_short(reports: tuple[SubjectReport, ...]) -> None:
    """Print one line per diagnostic on stdout, then the coverage and the summary on stderr.

    Args:
        reports: One report per subject the run checked.
    """
    diagnostics = render_short(reports)
    if diagnostics:
        typer.echo(diagnostics)
    _print_stderr(reports, with_prefixes=False)


def _print_stderr(reports: tuple[SubjectReport, ...], *, with_prefixes: bool) -> None:
    """Print the coverage, the per-prefix counts if asked, and the summary on stderr, each only when it holds a line.

    Args:
        reports: One report per subject the run checked.
        with_prefixes: True to print the errors and warnings of each code prefix before the summary.
    """
    coverage = render_coverage(reports)
    if coverage:
        typer.echo(coverage, err=True)
    if with_prefixes:
        prefixes = render_prefix_summary(reports)
        if prefixes:
            typer.echo(prefixes, err=True)
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
