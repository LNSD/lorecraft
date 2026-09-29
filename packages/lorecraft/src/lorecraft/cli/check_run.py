"""The steps every ``check`` command shares: the checks it can run, selecting the documents of one snapshot,
and printing what the checks found.

A check command is the composition root of its check: it calls ``select_documents``, hands what comes back to
its run, and hands the run to ``print_run``. Everything a check reads comes from the one snapshot
``select_documents`` takes, so a run sees a single moment of the tree even while files change under it.

Each check module also declares its check with ``register_check``, beside its command. That is how a bare
``lorecraft check`` finds every check to run without a list naming them: a new check module joins it by
registering, the way it joins the group by declaring its command.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import typer

from lorecraft.checks import CheckRun, Database, format_finding
from lorecraft_core.error import Error
from lorecraft_project.document import DocumentRef
from lorecraft_project.layout import SNAPSHOT_SCOPE
from lorecraft_vfs import take_snapshot

from .root import find_root, resolve_root
from .select import select_document

type CheckRunner = Callable[[Database, tuple[DocumentRef, ...]], CheckRun]
"""A check's run: it checks the documents it is handed, read through one database, and reports in one shape."""


@dataclass(frozen=True, slots=True)
class DocumentCheck:
    """One document check, as the ``check`` commands run and print it.

    Attributes:
        name: The check's subcommand, and its key in the JSON report of a bare ``lorecraft check``.
        run: Checks the selected documents.
        ungoverned: What the text line of an ungoverned document says after its rule, such as ``no header
            schema for this corpus; frontmatter unvalidated``.
    """

    name: str
    run: CheckRunner
    ungoverned: str


class DuplicateCheckError(RuntimeError):
    """Two different checks were registered under one name."""


_CHECKS: dict[str, DocumentCheck] = {}


def register_check(check: DocumentCheck) -> DocumentCheck:
    """Add a check to the ones a bare ``lorecraft check`` runs, and return it unchanged.

    Raises:
        DuplicateCheckError: If a different check already holds the name. Registering the same check again is
            a no-op, so a re-imported module is harmless.
    """
    registered = _CHECKS.get(check.name)
    if registered is not None and registered != check:
        raise DuplicateCheckError(f'check {check.name!r} is already registered')
    _CHECKS[check.name] = check
    return check


def registered_checks() -> tuple[DocumentCheck, ...]:
    """Every registered check, in name order, so the output of a bare ``lorecraft check`` is stable."""
    return tuple(_CHECKS[name] for name in sorted(_CHECKS))


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


def select_documents(root: Path | None, paths: list[Path] | None) -> tuple[Database, tuple[DocumentRef, ...]]:
    """Establish the root, snapshot it once, open the database over that snapshot, and select the documents.

    Args:
        root: The ``--root`` option; ``None`` searches upward from the working directory.
        paths: The documents named on the command line; ``None`` or empty selects every document the model
            lists.

    Raises:
        WorkingDirectoryError: If no root is given and the working directory cannot be read.
        RootError: If the root cannot be established.
        DocumentPathError: If a named path is not a document the model lists.
        Error: Any failure to take the snapshot or to load the model, as ``Database.model`` documents.
    """
    root_path = find_root(_working_directory()) if root is None else resolve_root(root)
    database = Database(take_snapshot(root_path, SNAPSHOT_SCOPE))
    model = database.model()
    if not paths:
        return database, model.documents()
    refs: list[DocumentRef] = []
    for argument in paths:
        refs.append(select_document(model, root_path, argument))
    return database, tuple(refs)


def print_run(run: CheckRun, output_format: Literal['text', 'json'], ungoverned: str) -> None:
    """Print one run: the JSON report on stdout, or a line per ungoverned document and finding on stdout and
    the summary line on stderr, both in the run's report order.

    Args:
        run: The run to print.
        output_format: ``text`` or ``json``.
        ungoverned: What the text line of an ungoverned document says after its rule, such as ``no header
            schema for this corpus; frontmatter unvalidated``.
    """
    if output_format == 'json':
        typer.echo(json.dumps(_json_report(run)))
        return
    _echo_lines(run, ungoverned)
    typer.echo(f'checked {len(run.reports)} file(s), {len(run.findings())} finding(s)', err=True)


def print_runs(runs: tuple[tuple[DocumentCheck, CheckRun], ...], output_format: Literal['text', 'json']) -> None:
    """Print the runs of every check over the same documents, check by check.

    The JSON report holds each check's own report, the one its subcommand prints, under the check's name. The
    text output is each check's lines in turn, then one summary line on stderr.

    Args:
        runs: Each check with its run, in the order to print them; every run covers the same documents.
        output_format: ``text`` or ``json``.
    """
    if output_format == 'json':
        report: dict[str, dict[str, object]] = {}
        for check, run in runs:
            report[check.name] = _json_report(run)
        typer.echo(json.dumps({'checks': report}))
        return

    findings = 0
    for check, run in runs:
        _echo_lines(run, check.ungoverned)
        findings += len(run.findings())
    checked = len(runs[0][1].reports) if runs else 0
    typer.echo(f'checked {checked} file(s) with {len(runs)} check(s), {findings} finding(s)', err=True)


def _json_report(run: CheckRun) -> dict[str, object]:
    """One run as its JSON report: the documents checked, every finding, and the ungoverned documents."""
    return {
        'checked': len(run.reports),
        'findings': [
            {
                'file': str(finding.path),
                'line': finding.line.value,
                'rule': finding.rule,
                'message': finding.message,
            }
            for finding in run.findings()
        ],
        'ungoverned': [str(report.ref.path) for report in run.reports if not report.governed],
    }


def _echo_lines(run: CheckRun, ungoverned: str) -> None:
    """Print a line per ungoverned document and per finding on stdout, in the run's report order."""
    for report in run.reports:
        if not report.governed:
            typer.echo(f'{report.ref.path}:1: [{report.ref.corpus}.ungoverned] {ungoverned}')
        for finding in report.findings():
            typer.echo(format_finding(finding))


def _working_directory() -> Path:
    """The current working directory, where the root search starts when no ``--root`` is given.

    Raises:
        WorkingDirectoryError: If the operating system cannot report it, such as after it was deleted.
    """
    try:
        return Path.cwd()
    except OSError as exc:
        raise WorkingDirectoryError(exc.strerror or str(exc)) from exc
