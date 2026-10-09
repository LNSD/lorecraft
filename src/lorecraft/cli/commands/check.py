"""The `check` command: run every enabled rule over the whole workspace, and report what the rules found.

This is the composition root of the rules engine. It loads the package's rules and parses `--select` and `--ignore`
against them, establishes the root, takes one snapshot, opens the database over it, selects every subject of the
workspace, builds the rule table from the rules and the selection, and hands the database, the subjects and the
table to the runner; what comes back is rendered by `diagnostics` and decides the exit code. Every `Error` escaping
that flow is reported here and exits 2; a file that does not decode is a diagnostic, not an error. A selection that
holds an alias code, or names a rule its level leaves off, is warned of on stderr, and the run goes on.
"""

from pathlib import Path
from typing import Annotated, assert_never

import typer

from lorecraft import rules
from lorecraft.checks import RuleTable, SubjectReport, check_subjects, selected_rules_left_off
from lorecraft.core.error import Error
from lorecraft.project.database import Database
from lorecraft.project.layout import SNAPSHOT_SCOPE
from lorecraft.rules.declaration import Severity
from lorecraft.rules.registry import Registry
from lorecraft.vfs import take_snapshot

from ..diagnostic_text import render_text
from ..diagnostics import render_coverage, render_json, render_prefix_summary, render_short, render_summary
from ..failure import report_failure
from ..output import ColorChoice, DiagnosticFormat, ExitStatus
from ..registry import register
from ..root import establish_root
from ..rule_selection import parse_rule_selection, print_selection_warnings
from ..sources import read_sources
from ..subjects import select_workspace
from ..terminal import detect_text_style, read_color_environment


@register('check')
def check(
    root: Annotated[
        Path | None,
        typer.Option('--root', help='Repository root. Defaults to the nearest parent containing docs/__meta__.'),
    ] = None,
    output_format: Annotated[
        DiagnosticFormat,
        typer.Option(
            '--format',
            help='Output format: text draws each diagnostic in full, short prints one line each, json prints one '
            'document.',
        ),
    ] = DiagnosticFormat.TEXT,
    color: Annotated[
        ColorChoice,
        typer.Option(
            '--color',
            metavar='<WHEN>',
            help='Control when colored output is used.\n\n'
            'auto: colour when stdout is an interactive terminal, unless NO_COLOR is set; FORCE_COLOR forces it.\n\n'
            'always: colour even when stdout is not a terminal.\n\n'
            'never: no colour.\n\n'
            'Only the text format is coloured.',
        ),
    ] = ColorChoice.AUTO,
    select: Annotated[
        list[str] | None,
        typer.Option(
            '--select',
            metavar='<selectors>',
            help='Run only these rules: codes, code or group prefixes, or ALL, comma-separated or repeated. Defaults '
            'to ALL.',
        ),
    ] = None,
    ignore: Annotated[
        list[str] | None,
        typer.Option(
            '--ignore',
            metavar='<selectors>',
            help='Skip these rules, unless a more specific selector selects them: codes, code or group prefixes, or '
            'ALL, comma-separated or repeated. Defaults to none.',
        ),
    ] = None,
) -> None:
    """Check every document and skill of the workspace: frontmatter, outline, length, links and layout.

    As text, each diagnostic is drawn on stdout with its source lines, labels, help and notes, coloured on a terminal.

    As short, each diagnostic is one uncoloured line on stdout: its path and line, severity, code and message.

    The ungoverned subjects and a summary go to stderr, with the errors and warnings per code prefix as text.

    As JSON, one compact document goes to stdout.

    --select never enables a rule its level leaves off; each such rule, and each alias code, is warned of on stderr.

    Exit 0 when no diagnostic is an error, 1 when any is, and 2 for invalid input, specifications or selectors.

    \f
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
