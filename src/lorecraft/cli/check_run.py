"""The steps every ``check`` command shares: the checks it can run, selecting the documents or the skills of one
snapshot, and printing what the checks found.

A check command is the composition root of its check: it calls ``select_documents``, hands what comes back to
its run, and hands the run to ``print_run``. Everything a check reads comes from the one snapshot
``select_documents`` takes, so a run sees a single moment of the tree even while files change under it. A check
over skills does the same with ``select_skills`` and ``print_skill_run``.

Each check module also declares its check with ``register_check``, or ``register_skill_check``, beside its
command. That is how a bare ``lorecraft check`` finds every check to run without a list naming them: a new check
module joins it by registering, the way it joins the group by declaring its command.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import typer

from lorecraft.checks import CheckRun, Database, Finding, SkillCheckRun, format_finding
from lorecraft.core.error import Error
from lorecraft.project.document import DocumentRef
from lorecraft.project.layout import SNAPSHOT_SCOPE
from lorecraft.project.skill import SkillRef
from lorecraft.vfs import take_snapshot

from .root import find_root, resolve_root
from .select import select_document, select_skills_at

type CheckRunner = Callable[[Database, tuple[DocumentRef, ...]], CheckRun]
"""A check's run: it checks the documents it is handed, read through one database, and reports in one shape."""


@dataclass(frozen=True, slots=True)
class DocumentCheck:
    """One document check, as the ``check`` commands run and print it.

    Attributes:
        name: The check's subcommand, and its key in the JSON report of a bare ``lorecraft check``.
        run: Checks the selected documents.
        ungoverned: What the text line of an ungoverned document says after its rule, such as ``no
            frontmatter schema for this corpus; frontmatter unvalidated``.
    """

    name: str
    run: CheckRunner
    ungoverned: str


type SkillCheckRunner = Callable[[Database, tuple[SkillRef, ...]], SkillCheckRun]
"""A skill check's run: it checks the skills it is handed, read through one database."""


@dataclass(frozen=True, slots=True)
class SkillCheck:
    """One skill check, as the ``check`` commands run and print it. A skill is never ungoverned.

    Attributes:
        name: The check's subcommand, and its key in the JSON report of a bare ``lorecraft check``.
        run: Checks the selected skills.
    """

    name: str
    run: SkillCheckRunner


class DuplicateCheckError(RuntimeError):
    """Two different checks were registered under one name."""


_CHECKS: dict[str, DocumentCheck] = {}
_SKILL_CHECKS: dict[str, SkillCheck] = {}


def register_check(check: DocumentCheck) -> DocumentCheck:
    """Add a check to the ones a bare ``lorecraft check`` runs, and return it unchanged.

    Raises:
        DuplicateCheckError: If a different check already holds the name. Registering the same check again is
            a no-op, so a re-imported module is harmless.
    """
    registered = _CHECKS.get(check.name)
    if (registered is not None and registered != check) or check.name in _SKILL_CHECKS:
        raise DuplicateCheckError(f'check {check.name!r} is already registered')
    _CHECKS[check.name] = check
    return check


def registered_checks() -> tuple[DocumentCheck, ...]:
    """Every registered document check, in name order, so the output of a bare ``lorecraft check`` is stable."""
    return tuple(_CHECKS[name] for name in sorted(_CHECKS))


def register_skill_check(check: SkillCheck) -> SkillCheck:
    """Add a skill check to the ones a bare ``lorecraft check`` runs, and return it unchanged.

    Raises:
        DuplicateCheckError: If a different check, over skills or over documents, already holds the name.
            Registering the same check again is a no-op, so a re-imported module is harmless.
    """
    registered = _SKILL_CHECKS.get(check.name)
    if (registered is not None and registered != check) or check.name in _CHECKS:
        raise DuplicateCheckError(f'check {check.name!r} is already registered')
    _SKILL_CHECKS[check.name] = check
    return check


def registered_skill_checks() -> tuple[SkillCheck, ...]:
    """Every registered skill check, in name order, so the output of a bare ``lorecraft check`` is stable."""
    return tuple(_SKILL_CHECKS[name] for name in sorted(_SKILL_CHECKS))


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
        WorkingDirectoryError: If no root is given, or a path is named, and the working directory cannot be read.
        RootError: If the root cannot be established.
        LinkedLayoutError: If ``docs/`` or ``docs/__meta__/`` under the root is a symlink.
        DocumentPathError: If a named path is not a document the model lists.
        Error: Any failure to take the snapshot or to load the model, as ``Database.model`` documents.
    """
    root_path = find_root(_working_directory()) if root is None else resolve_root(root)
    database = Database(take_snapshot(root_path, SNAPSHOT_SCOPE))
    # Root discovery follows symlinks and the snapshot, under `docs/`, does not, so a linked `docs/__meta__/`
    # passes the first and is empty in the second. Refused here, before a run over no documents can report
    # success.
    database.require_real_layout()
    model = database.model()
    if not paths:
        return database, model.documents()
    working_directory = _working_directory()
    refs: list[DocumentRef] = []
    for argument in paths:
        refs.append(select_document(database, root_path, working_directory, argument))
    return database, tuple(refs)


def select_skills(root: Path | None, paths: list[Path] | None) -> tuple[Database, tuple[SkillRef, ...]]:
    """Establish the root, snapshot it once, open the database over that snapshot, and select the skills.

    Args:
        root: The ``--root`` option; ``None`` searches upward from the working directory.
        paths: The skills named on the command line, each by its directory or its ``SKILL.md``; ``None`` or
            empty selects every skill the model lists. A skill two paths name is selected once.

    Raises:
        WorkingDirectoryError: If no root is given, or a path is named, and the working directory cannot be read.
        RootError: If the root cannot be established.
        SkillPathError: If a named path is not a skill the model lists.
        Error: Any failure to take the snapshot or to load the model, as ``Database.model`` documents.
    """
    root_path = find_root(_working_directory()) if root is None else resolve_root(root)
    database = Database(take_snapshot(root_path, SNAPSHOT_SCOPE))
    if not paths:
        return database, database.model().skills()
    working_directory = _working_directory()
    refs: list[SkillRef] = []
    for argument in paths:
        for ref in select_skills_at(database, root_path, working_directory, argument):
            if ref not in refs:
                refs.append(ref)
    return database, tuple(refs)


def print_run(run: CheckRun, output_format: Literal['text', 'json'], ungoverned: str) -> None:
    """Print one run: the JSON report on stdout, or a line per ungoverned document and finding on stdout and
    the summary line on stderr, both in the run's report order.

    Args:
        run: The run to print.
        output_format: ``text`` or ``json``.
        ungoverned: What the text line of an ungoverned document says after its rule, such as ``no
            frontmatter schema for this corpus; frontmatter unvalidated``.
    """
    if output_format == 'json':
        typer.echo(json.dumps(_json_report(run)))
        return
    _echo_lines(run, ungoverned)
    typer.echo(f'checked {len(run.reports)} file(s), {len(run.findings())} finding(s)', err=True)


def print_skill_run(run: SkillCheckRun, output_format: Literal['text', 'json']) -> None:
    """Print one skill run: the JSON report on stdout, or a line per finding on stdout and the summary line on
    stderr, both in the run's report order.

    Args:
        run: The run to print.
        output_format: ``text`` or ``json``.
    """
    if output_format == 'json':
        typer.echo(json.dumps(_json_skill_report(run)))
        return
    for finding in run.findings():
        typer.echo(format_finding(finding))
    typer.echo(f'checked {len(run.reports)} skill(s), {len(run.findings())} finding(s)', err=True)


def print_runs(
    runs: tuple[tuple[DocumentCheck, CheckRun], ...],
    skill_runs: tuple[tuple[SkillCheck, SkillCheckRun], ...],
    output_format: Literal['text', 'json'],
) -> None:
    """Print the runs of every check, check by check: the document checks, then the skill checks.

    The JSON report holds each check's own report, the one its subcommand prints, under the check's name. The
    text output is each check's lines in turn, then one summary line on stderr counting the documents and
    the skills apart.

    Args:
        runs: Each document check with its run, in the order to print them; every run covers the same
            documents.
        skill_runs: Each skill check with its run, in the order to print them; every run covers the same
            skills.
        output_format: ``text`` or ``json``.
    """
    if output_format == 'json':
        report: dict[str, dict[str, object]] = {}
        for check, run in runs:
            report[check.name] = _json_report(run)
        for skill_check, skill_run in skill_runs:
            report[skill_check.name] = _json_skill_report(skill_run)
        typer.echo(json.dumps({'checks': report}))
        return

    findings = 0
    for check, run in runs:
        _echo_lines(run, check.ungoverned)
        findings += len(run.findings())
    for _skill_check, skill_run in skill_runs:
        for finding in skill_run.findings():
            typer.echo(format_finding(finding))
        findings += len(skill_run.findings())
    files = len(runs[0][1].reports) if runs else 0
    skills = len(skill_runs[0][1].reports) if skill_runs else 0
    checks = len(runs) + len(skill_runs)
    typer.echo(f'checked {files} file(s) and {skills} skill(s) with {checks} check(s), {findings} finding(s)', err=True)


def _json_report(run: CheckRun) -> dict[str, object]:
    """One run as its JSON report: the documents checked, every finding, and the ungoverned documents."""
    return {
        'checked': len(run.reports),
        'findings': _json_findings(run.findings()),
        'ungoverned': [str(report.ref.path) for report in run.reports if not report.governed],
    }


def _json_skill_report(run: SkillCheckRun) -> dict[str, object]:
    """One skill run as its JSON report, in the shape of a document check's.

    ``ungoverned`` is always empty, since the Agent Skills specification governs every skill; it is kept so a
    reader of a bare ``lorecraft check`` report reads every check the same way.
    """
    ungoverned: list[str] = []
    return {
        'checked': len(run.reports),
        'findings': _json_findings(run.findings()),
        'ungoverned': ungoverned,
    }


def _json_findings(findings: tuple[Finding, ...]) -> list[dict[str, object]]:
    """The findings as JSON objects, in the order given."""
    objects: list[dict[str, object]] = []
    for finding in findings:
        objects.append(
            {
                'file': str(finding.path),
                'line': finding.line.value,
                'rule': finding.rule,
                'message': finding.message,
                'spec': None if finding.spec is None else str(finding.spec),
            }
        )
    return objects


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
