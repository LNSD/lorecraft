"""The flow behind `lorecraft check`: run every enabled rule over the whole workspace, and report what the rules found.

This is the composition root of the rules engine. `--select` and `--ignore` arrive parsed and confirmed against the rule
index; it loads the package's rules and builds the selection from them, establishes the root, takes one snapshot,
opens the database over it, stops when `docs/` or `docs/__meta__/` could not be listed, selects every subject of the
workspace, builds the rule table from the rules and the selection, and hands the database, the subjects and the
table to the runner, beside the reports for retained refusals and units that failed to load; what comes back is
rendered by `diagnostics` and decides the exit code. A file that does not decode, a load failure, or a retained
refusal under `docs/` is a diagnostic, and a run that reports one exits 1. Subjects whose resolved files have a
retained docs refusal are skipped because that path already has a diagnostic. A refusal outside `docs/` that the
model does not report, or an `Error` escaping the flow, is reported here and exits 2; unlistable `docs/` and
`docs/__meta__/` also exit 2. A selection that holds an alias code, or names a rule its level leaves off, is warned
of on stderr, and the run goes on.

It lives apart from `commands/check.py` so that importing the command, which `--help` and `--version` do, does not
import the rules engine: the command imports this module only when it runs.
"""

from collections.abc import Mapping
from pathlib import Path
from typing import assert_never

import typer

from lorecraft import rules
from lorecraft.core.error import Error
from lorecraft.core.path import RootRelativePath
from lorecraft.engine import UnlistableRoot, check_subjects, report_load_failures
from lorecraft.project.database import Database
from lorecraft.project.document import DocumentRef, SpecRef
from lorecraft.project.layout import DECLARATION, DOCS_DIR, SNAPSHOT_SCOPE
from lorecraft.project.workspace import WorkspaceModel, reject_unreported_refusals
from lorecraft.rules.engine import RefusedOperation
from lorecraft.rules.engine.unreadable_path import Refused, UnreadablePath
from lorecraft.rules.identity import Severity
from lorecraft.rules.registry import Registry
from lorecraft.rules.report import LoadFailureReport, RunReport, UnreadableDocument
from lorecraft.rules.table import RuleTable, selected_rules_left_off
from lorecraft.vfs import RefusedInspect, RefusedListing, RefusedRead, RefusedRecord, take_snapshot

from .diagnostic_text import render_text
from .diagnostics import render_coverage, render_json, render_prefix_summary, render_short, render_summary
from .failure import report_failure, report_load_failure
from .output import ColorChoice, DiagnosticFormat, ExitStatus
from .root import establish_root
from .rule_arguments import SelectorValue
from .rule_selection import build_rule_selection, print_selection_warnings
from .sources import read_sources
from .subjects import select_workspace
from .terminal import detect_text_style, read_color_environment


def run_check(
    root: Path | None,
    *,
    output_format: DiagnosticFormat,
    color: ColorChoice,
    select: list[SelectorValue] | None,
    ignore: list[SelectorValue] | None,
) -> ExitStatus | None:
    """Run the rules over the workspace and write the report; the body of `lorecraft check`.

    Args:
        root: The `--root` option; `None` searches upward from the working directory.
        output_format: How the diagnostics are written.
        color: When to emphasise the text format with colour.
        select: The `--select` values, already parsed and confirmed against the rule index.
        ignore: The `--ignore` values, already parsed and confirmed against the rule index.

    Returns:
        `ExitStatus.FINDINGS` when any diagnostic is an error, `ExitStatus.FAILURE` for invalid input, an
        unreported refusal outside `docs/`, or when `docs/` or `docs/__meta__/` cannot be listed, which the
        command handler exits with; `None` otherwise.

    Raises:
        RuntimeError: If the rules cannot be registered, or a selector names a group or a code the registry does not
            hold, which means the generated index is stale.
    """
    try:
        registry = Registry.load(rules)
        parsed = build_rule_selection(registry, select=select, ignore=ignore)
        print_selection_warnings(parsed, selected_rules_left_off(registry, parsed.selection))
        # Root discovery follows symlinks and the snapshot, under `docs/`, does not, so a linked `docs/__meta__/`
        # passes the first and is empty in the second. `from_snapshot` refuses it, before a run over no documents can
        # report success.
        database = Database.from_snapshot(take_snapshot(establish_root(root), SNAPSHOT_SCOPE, declaration=DECLARATION))
        # With no corpus and no meta spec known, nothing can be checked, so this stops before any subject is selected.
        # Every other failure the model recorded is reported below, as a diagnostic.
        model = database.model()
        load_failure_reports = _reports_or_status(model)
        if isinstance(load_failure_reports, ExitStatus):
            return load_failure_reports
        refusals = database.refusals()
        docs_refusals = database.unreported_docs_refusals()
        all_docs_refusals = {path: refusal for path, refusal in refusals.items() if path.is_relative_to(DOCS_DIR)}
        non_docs_refusals = {path: refusal for path, refusal in refusals.items() if not path.is_relative_to(DOCS_DIR)}
        reject_unreported_refusals(non_docs_refusals, model)
        documents = {ref.path: ref for ref in (*model.documents(), *model.specifications())}
        refusal_reports = _refusal_reports(docs_refusals, documents)
        subjects = select_workspace(database)
        table = RuleTable.from_registry(registry, parsed.selection)
        reports = (
            *load_failure_reports,
            *refusal_reports,
            *check_subjects(database, subjects, table, all_docs_refusals),
        )
    except Error as exc:
        report_failure(exc)
        return ExitStatus.FAILURE

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
        return ExitStatus.FINDINGS
    return None


def _reports_or_status(model: WorkspaceModel) -> tuple[RunReport, ...] | ExitStatus:
    """The report of each unit that failed to load, or the failure status when the root cannot be listed.

    Args:
        model: The workspace model the run loaded.

    Returns:
        The reports, or `ExitStatus.FAILURE` when `docs/` or `docs/__meta__/` could not be listed.
    """
    load_failures = report_load_failures(model)
    match load_failures:
        case UnlistableRoot(failure=failure):
            report_load_failure(failure)
            return ExitStatus.FAILURE
        case tuple() as load_failure_reports:
            return load_failure_reports
        case _:
            assert_never(load_failures)


def _refusal_reports(
    refusals: Mapping[RootRelativePath, RefusedRecord], documents: Mapping[RootRelativePath, DocumentRef | SpecRef]
) -> tuple[RunReport, ...]:
    """Report retained refusals under `docs/`, keeping unreadable documents and meta specifications as subjects.

    Args:
        refusals: Docs refusals the model has not already reported as load failures.
        documents: Governed documents and meta specifications keyed by path, used to preserve their subject counts.
    """
    reports: list[RunReport] = []
    for path, refusal in refusals.items():
        match refusal:
            case RefusedRead(refusal=reason):
                operation = RefusedOperation.READ
            case RefusedListing(refusal=reason):
                operation = RefusedOperation.LIST
            case RefusedInspect(refusal=reason):
                operation = RefusedOperation.INSPECT
            case _:
                assert_never(refusal)
        occurrence = UnreadablePath(failed_at=path, cause=Refused(operation, reason))
        document = documents.get(path)
        if isinstance(refusal, RefusedRead) and document is not None:
            reports.append(UnreadableDocument(document, occurrence))
        else:
            reports.append(LoadFailureReport(path, occurrence))
    return tuple(reports)


def _print_text(reports: tuple[RunReport, ...], database: Database, color: ColorChoice) -> None:
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


def _print_short(reports: tuple[RunReport, ...]) -> None:
    """Print one line per diagnostic on stdout, then the coverage and the summary on stderr.

    Args:
        reports: One report per subject the run checked.
    """
    diagnostics = render_short(reports)
    if diagnostics:
        typer.echo(diagnostics)
    _print_stderr(reports, with_prefixes=False)


def _print_stderr(reports: tuple[RunReport, ...], *, with_prefixes: bool) -> None:
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


def _has_error(reports: tuple[RunReport, ...]) -> bool:
    """True when any diagnostic of any report is an error; warnings alone let a run pass.

    Args:
        reports: One report per subject the run checked.
    """
    for report in reports:
        for diagnostic in report.diagnostics:
            if diagnostic.severity is Severity.ERROR:
                return True
    return False
