"""The steps every `check` command shares.

They are the checks it can run, selecting the documents or the skills of one snapshot, and printing what the
checks found.

A check command is the composition root of its check: it calls `select_documents`, hands what comes back to
its run, and hands the run to `print_run`. Everything a check reads comes from the one snapshot
`select_documents` takes, so a run sees a single moment of the tree even while files change under it. A check
over skills does the same with `select_skills` and `print_skill_run`.

Each check module also declares its check with `register_check`, or `register_skill_check`, beside its
command. That is how a bare `lorecraft check` finds every check to run without a list naming them: a new check
module joins it by registering, the way it joins the group by declaring its command.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import assert_never

import typer

from lorecraft.checks import (
    CheckRun,
    Database,
    Finding,
    GovernedDocumentReport,
    SkillCheckRun,
    SkillScope,
    SkillSelection,
    UngovernedDocumentReport,
    format_finding,
)
from lorecraft.core.error import Error
from lorecraft.project.document import DocumentRef
from lorecraft.project.layout import SNAPSHOT_SCOPE, scope_with_named_dirs
from lorecraft.vfs import OsRefusal, take_snapshot

from .output import OutputFormat
from .root import get_root, resolve_root
from .select import named_skill_dirs, select_document, select_skills_at, select_whole

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


type SkillCheckRunner = Callable[[Database, tuple[SkillSelection, ...]], SkillCheckRun]
"""A skill check's run: it checks the skills it is handed, each whole or by its `SKILL.md` alone, read through one
database."""


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
    """Two different checks were registered under one name: a defect in the package, never the user's input.

    Attributes:
        name: The name both checks claim.
    """

    name: str

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f'check {name!r} is already registered')


_CHECKS: dict[str, DocumentCheck] = {}
_SKILL_CHECKS: dict[str, SkillCheck] = {}


def register_check(check: DocumentCheck) -> DocumentCheck:
    """Add a check to the ones a bare `lorecraft check` runs, and return it unchanged.

    Args:
        check: The document check to register, keyed by its `name`.

    Raises:
        DuplicateCheckError: If a different check already holds the name. Registering the same check again is
            a no-op, so a re-imported module is harmless.
    """
    registered = _CHECKS.get(check.name)
    if (registered is not None and registered != check) or check.name in _SKILL_CHECKS:
        raise DuplicateCheckError(check.name)
    _CHECKS[check.name] = check
    return check


def registered_checks() -> tuple[DocumentCheck, ...]:
    """Every registered document check, in name order, so the output of a bare ``lorecraft check`` is stable."""
    return tuple(_CHECKS[name] for name in sorted(_CHECKS))


def register_skill_check(check: SkillCheck) -> SkillCheck:
    """Add a skill check to the ones a bare `lorecraft check` runs, and return it unchanged.

    Args:
        check: The skill check to register, keyed by its `name`, which document checks share.

    Raises:
        DuplicateCheckError: If a different check, over skills or over documents, already holds the name.
            Registering the same check again is a no-op, so a re-imported module is harmless.
    """
    registered = _SKILL_CHECKS.get(check.name)
    if (registered is not None and registered != check) or check.name in _CHECKS:
        raise DuplicateCheckError(check.name)
    _SKILL_CHECKS[check.name] = check
    return check


def registered_skill_checks() -> tuple[SkillCheck, ...]:
    """Every registered skill check, in name order, so the output of a bare ``lorecraft check`` is stable."""
    return tuple(_SKILL_CHECKS[name] for name in sorted(_SKILL_CHECKS))


class WorkingDirectoryReadError(Error):
    """The current working directory cannot be read, so no root can be searched for from it.

    That happens, for one, after the directory was deleted.

    Attributes:
        refusal: Why the operating system refused to report it.
        source: The operating system's failure.
    """

    refusal: OsRefusal
    source: OSError

    def __init__(self, refusal: OsRefusal, *, source: OSError) -> None:
        self.refusal = refusal
        self.source = source
        super().__init__(f'cannot read the current directory: {refusal.value}')
        self.__cause__ = source


def select_documents(root: Path | None, paths: list[Path] | None) -> tuple[Database, tuple[DocumentRef, ...]]:
    """Establish the root, snapshot it once, open the database over that snapshot, and select the documents.

    Args:
        root: The ``--root`` option; ``None`` searches upward from the working directory.
        paths: The documents named on the command line; ``None`` or empty selects every document the model
            lists. A document two paths name, however each spells it, is selected once, at its first place.

    Raises:
        WorkingDirectoryReadError: If no root is given, or a path is named, and the working directory cannot be read.
        RootNotFoundError: If no root is given and no directory upward holds docs/__meta__/.
        RootCandidateInspectError: If no root is given and a directory upward cannot be inspected.
        InvalidRootError: If the given root is not an existing directory.
        RootInspectError: If the given root cannot be inspected.
        SnapshotDirListError: If a directory in scope cannot be listed.
        SnapshotEntryInspectError: If an entry on the way to a scope root cannot be inspected.
        SnapshotFileReadError: If a file in scope cannot be read.
        SnapshotLinkReadError: If a symlink's target cannot be read.
        LinkedLayoutError: If ``docs/`` or ``docs/__meta__/`` under the root is a symlink.
        DirListError: If the specification directory or docs/ cannot be listed.
        CorpusListError: If a corpus directory cannot be listed.
        StructureSchemaReadError: If any structure specification cannot be read.
        StructureSpecDecodeError: If a structure specification is not JSON in the dialect's shape.
        StructureSpecFilenameError: If a structure specification is not at a specification filename.
        EmptyStructureSpecError: If a structure specification states no rule.
        InvalidTitleCountError: If a title count is below 1.
        InvalidTokenBudgetError: If a token budget is below 1.
        InvalidWordCapError: If an outline word cap is below 1.
        RepeatedOutlineSectionError: If an outline names a section twice.
        ForbiddenOutlineSectionError: If a specification forbids a section its outline names.
        AdjacentAnyRunsError: If an outline places two ``any`` runs side by side.
        InvalidFrontmatterSchemaError: If a frontmatter schema is rejected by the meta-schema.
        FrontmatterSchemaIdError: If a schema in a frontmatter schema carries ``$id``.
        ForeignFrontmatterDialectError: If a schema in a frontmatter schema names another dialect.
        UntypedFrontmatterSchemaError: If a frontmatter schema's root does not state an object.
        DirResolveError: If a skills directory cannot be resolved.
        EntryInspectError: If an entry on the way to a skills directory cannot be inspected, or a link's target
            read, while looking for where it leaves the repository.
        SkillsDirListError: If a skills directory cannot be listed.
        SkillEntryResolveError: If a symlinked skill entry cannot be resolved.
        SkillDirListError: If a skill directory cannot be listed.
        SkillFileResolveError: If a symlinked SKILL.md cannot be resolved.
        NonFileDocumentPathError: If a named path leads to a directory.
        NonMarkdownDocumentPathError: If a named path is not a ``.md`` file.
        OutsideDocsDocumentPathError: If a named path lies outside ``docs/`` or inside ``docs/__meta__/``.
        CorpuslessDocumentPathError: If a named path sits directly in ``docs/``.
        InvalidCorpusDocumentPathError: If a named path's corpus directory is not a valid corpus name.
        UnknownCorpusDocumentPathError: If a named path's corpus directory is not a corpus.
        NestedDocumentPathError: If a named path sits in a subdirectory of its corpus.
        MissingDocumentPathError: If the snapshot holds no file at a named path.
        UnlistedDocumentPathError: If a named path is not a document the model lists.
    """
    root_path = get_root(_working_directory()) if root is None else resolve_root(root)
    database = Database(take_snapshot(root_path, SNAPSHOT_SCOPE))
    # Root discovery follows symlinks and the snapshot, under `docs/`, does not, so a linked `docs/__meta__/`
    # passes the first and is empty in the second. Refused here, before a run over no documents can report
    # success.
    database.reject_linked_layout()
    model = database.model()
    if not paths:
        return database, model.documents()
    working_directory = _working_directory()
    refs: list[DocumentRef] = []
    for argument in paths:
        ref = select_document(database, root_path, working_directory, argument)
        if ref not in refs:
            refs.append(ref)
    return database, tuple(refs)


def select_skills(root: Path | None, paths: list[Path] | None) -> tuple[Database, tuple[SkillSelection, ...]]:
    """Establish the root, snapshot it once, open the database over that snapshot, and select the skills.

    The directories the paths name are spelled first, so the one snapshot reads them beside the agents' skills
    directories and the model lists the skills in them.

    Args:
        root: The `--root` option; `None` searches upward from the working directory.
        paths: The skills named on the command line, each by a skills directory, a skill directory, or a
            `SKILL.md`; `None` or empty selects every skill in the agents' skills directories, whole. A path
            naming an agent's skills directory selects every skill listed in it, possibly none; one naming an
            entry of it selects that skill alone. Any other directory is one skill when a `SKILL.md` is at its
            root, and otherwise selects each skill directly inside it, under the path as spelled; one holding
            none is refused. A directory selects each skill whole, a `SKILL.md` its `SKILL.md` alone. A skill two
            paths name is selected once, at its first place, and whole when either path names it whole.

    Raises:
        WorkingDirectoryReadError: If no root is given, or a path is named, and the working directory cannot be read.
        RootNotFoundError: If no root is given and no directory upward holds docs/__meta__/.
        RootCandidateInspectError: If no root is given and a directory upward cannot be inspected.
        InvalidRootError: If the given root is not an existing directory.
        RootInspectError: If the given root cannot be inspected.
        SnapshotDirListError: If a directory in scope cannot be listed.
        SnapshotEntryInspectError: If an entry on the way to a scope root cannot be inspected.
        SnapshotFileReadError: If a file in scope cannot be read.
        SnapshotLinkReadError: If a symlink's target cannot be read.
        LinkedLayoutError: If `docs/` or `docs/__meta__/` under the root is a symlink.
        DirListError: If the specification directory or docs/ cannot be listed.
        CorpusListError: If a corpus directory cannot be listed.
        StructureSchemaReadError: If any structure specification cannot be read.
        StructureSpecDecodeError: If a structure specification is not JSON in the dialect's shape.
        StructureSpecFilenameError: If a structure specification is not at a specification filename.
        EmptyStructureSpecError: If a structure specification states no rule.
        InvalidTitleCountError: If a title count is below 1.
        InvalidTokenBudgetError: If a token budget is below 1.
        InvalidWordCapError: If an outline word cap is below 1.
        RepeatedOutlineSectionError: If an outline names a section twice.
        ForbiddenOutlineSectionError: If a specification forbids a section its outline names.
        AdjacentAnyRunsError: If an outline places two `any` runs side by side.
        InvalidFrontmatterSchemaError: If a frontmatter schema is rejected by the meta-schema.
        FrontmatterSchemaIdError: If a schema in a frontmatter schema carries `$id`.
        ForeignFrontmatterDialectError: If a schema in a frontmatter schema names another dialect.
        UntypedFrontmatterSchemaError: If a frontmatter schema's root does not state an object.
        DirResolveError: If a skills directory or a directory a path names cannot be resolved.
        EntryInspectError: If an entry on the way to a skills directory cannot be inspected, or a link's target
            read, while looking for where it leaves the repository.
        SkillsDirListError: If a skills directory cannot be listed.
        SkillEntryResolveError: If a symlinked skill entry cannot be resolved.
        SkillDirListError: If a skill directory cannot be listed.
        SkillFileResolveError: If a symlinked SKILL.md cannot be resolved.
        UnlistedSkillPathError: If a named path is not a skill the model lists.
    """
    root_path = get_root(_working_directory()) if root is None else resolve_root(root)
    if not paths:
        database = Database(take_snapshot(root_path, SNAPSHOT_SCOPE))
        return database, select_whole(database.model().skills())
    working_directory = _working_directory()
    named_dirs = named_skill_dirs(root_path, working_directory, paths)
    # The snapshot records the scope it was taken of, so the model reads the named directories from it.
    database = Database(take_snapshot(root_path, scope_with_named_dirs(named_dirs)))
    named: list[SkillSelection] = []
    for argument in paths:
        named.extend(select_skills_at(database, root_path, working_directory, argument))
    return database, merge_selections(tuple(named))


def merge_selections(selections: tuple[SkillSelection, ...]) -> tuple[SkillSelection, ...]:
    """The selections with one per skill, each at the place its skill was first named.

    A whole selection replaces one of the same skill's `SKILL.md` alone, wherever either comes, since checking
    the whole skill checks its `SKILL.md` too.

    Args:
        selections: What each path named, in the order the paths were given.
    """
    merged: list[SkillSelection] = []
    for selection in selections:
        _add_selection(merged, selection)
    return tuple(merged)


def _add_selection(selections: list[SkillSelection], selection: SkillSelection) -> None:
    """Add a selection to the ones merged so far, by the rule `merge_selections` states.

    Args:
        selections: The selections merged so far, in the order their skills were first named; updated in place.
        selection: The next selection to merge.
    """
    for index, selected in enumerate(selections):
        if selected.ref == selection.ref:
            if selection.scope is SkillScope.WHOLE_SKILL:
                selections[index] = selection
            return
    selections.append(selection)


def print_run(run: CheckRun, output_format: OutputFormat, ungoverned: str) -> None:
    """Print one run, in the run's report order.

    The JSON report goes to stdout. As text, a line per ungoverned document and finding goes to stdout and the
    summary line to stderr.

    Args:
        run: The run to print.
        output_format: Whether to print the run as text or as JSON.
        ungoverned: What the text line of an ungoverned document says after its rule, such as ``no
            frontmatter schema for this corpus; frontmatter unvalidated``.
    """
    match output_format:
        case OutputFormat.TEXT:
            _echo_lines(run, ungoverned)
            typer.echo(f'checked {len(run.reports)} file(s), {len(run.findings())} finding(s)', err=True)
        case OutputFormat.JSON:
            typer.echo(json.dumps(_json_report(run)))
        case _:
            assert_never(output_format)


def print_skill_run(run: SkillCheckRun, output_format: OutputFormat) -> None:
    """Print one skill run, in the run's report order.

    The JSON report goes to stdout. As text, a line per finding goes to stdout and the summary line to stderr.

    Args:
        run: The run to print.
        output_format: Whether to print the run as text or as JSON.
    """
    match output_format:
        case OutputFormat.TEXT:
            for finding in run.findings():
                typer.echo(format_finding(finding))
            typer.echo(f'checked {len(run.reports)} skill(s), {len(run.findings())} finding(s)', err=True)
        case OutputFormat.JSON:
            typer.echo(json.dumps(_json_skill_report(run)))
        case _:
            assert_never(output_format)


def print_runs(
    runs: tuple[tuple[DocumentCheck, CheckRun], ...],
    skill_runs: tuple[tuple[SkillCheck, SkillCheckRun], ...],
    output_format: OutputFormat,
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
        output_format: Whether to print the runs as text or as JSON.
    """
    match output_format:
        case OutputFormat.TEXT:
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
            summary = f'checked {files} file(s) and {skills} skill(s) with {checks} check(s), {findings} finding(s)'
            typer.echo(summary, err=True)
        case OutputFormat.JSON:
            report: dict[str, dict[str, object]] = {}
            for check, run in runs:
                report[check.name] = _json_report(run)
            for skill_check, skill_run in skill_runs:
                report[skill_check.name] = _json_skill_report(skill_run)
            typer.echo(json.dumps({'checks': report}))
        case _:
            assert_never(output_format)


def _json_report(run: CheckRun) -> dict[str, object]:
    """One run as its JSON report: the documents checked, every finding, and the ungoverned documents.

    Args:
        run: The run to report; its reports give the checked count and which documents are ungoverned.
    """
    ungoverned: list[str] = []
    for report in run.reports:
        match report:
            case GovernedDocumentReport():
                pass
            case UngovernedDocumentReport():
                ungoverned.append(str(report.ref.path))
            case _:
                assert_never(report)
    return {
        'checked': len(run.reports),
        'findings': _json_findings(run.findings()),
        'ungoverned': ungoverned,
    }


def _json_skill_report(run: SkillCheckRun) -> dict[str, object]:
    """One skill run as its JSON report, in the shape of a document check's.

    `ungoverned` is always empty, since the Agent Skills specification governs every skill; it is kept so a
    reader of a bare `lorecraft check` report reads every check the same way.

    Args:
        run: The skill run to report; its reports give the checked count.
    """
    ungoverned: list[str] = []
    return {
        'checked': len(run.reports),
        'findings': _json_findings(run.findings()),
        'ungoverned': ungoverned,
    }


def _json_findings(findings: tuple[Finding, ...]) -> list[dict[str, object]]:
    """The findings as JSON objects, in the order given.

    Every object carries `notes`, an empty list for a finding without any, so each has the same keys.

    Args:
        findings: The findings to encode; each becomes one object, in this order.
    """
    objects: list[dict[str, object]] = []
    for finding in findings:
        notes: list[dict[str, str]] = []
        for note in finding.notes:
            notes.append({'kind': note.kind.value, 'text': note.text})
        objects.append(
            {
                'file': str(finding.path),
                'line': finding.line.value,
                'rule': finding.rule,
                'message': finding.message,
                'spec': None if finding.spec is None else str(finding.spec),
                'notes': notes,
            }
        )
    return objects


def _echo_lines(run: CheckRun, ungoverned: str) -> None:
    """Print a line per ungoverned document and per finding on stdout, in the run's report order.

    Args:
        run: The run whose reports are printed.
        ungoverned: Text of an ungoverned document's line after its rule, as `DocumentCheck.ungoverned` states it.
    """
    for report in run.reports:
        match report:
            case GovernedDocumentReport():
                for finding in report.findings():
                    typer.echo(format_finding(finding))
            case UngovernedDocumentReport():
                typer.echo(f'{report.ref.path}:1: [{report.ref.corpus}.ungoverned] {ungoverned}')
            case _:
                assert_never(report)


def _working_directory() -> Path:
    """The current working directory, where the root search starts when no ``--root`` is given.

    Raises:
        WorkingDirectoryReadError: If the operating system cannot report it, such as after it was deleted.
    """
    try:
        return Path.cwd()
    except OSError as exc:
        raise WorkingDirectoryReadError(OsRefusal.from_error(exc), source=exc) from exc
