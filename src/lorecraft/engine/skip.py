"""Run checks over workspace subjects, skipping files whose required input was refused.

A document or skill entry governed by a meta spec that failed to load cannot be called clean from only the layers that
loaded. It is decoded first, and a decoded item is skipped with the failed structure paths. A skill or resource whose
resolved docs target was refused is also skipped; the refusal itself is reported at its target.
"""

from collections.abc import Iterable, Mapping
from typing import assert_never

from lorecraft.core.path import RootRelativePath
from lorecraft.project.database import Database, DocumentText, SkillText, Undecodable
from lorecraft.project.document import DocumentRef
from lorecraft.project.item import MarkdownItemRef
from lorecraft.project.layout import DOCS_DIR
from lorecraft.project.skill import OutsideSymlink, SkillLocation, SkillResourceLocation
from lorecraft.rules.report import SkippedSubject, SubjectReport, UndecodableSubject
from lorecraft.rules.table import RuleTable
from lorecraft.vfs import RefusedRead, RefusedRecord

from .runner import RefusedSkillSubject, Subject, check_layout_entry, check_skill_resource, judge_item


def check_subjects(
    database: Database,
    subjects: Iterable[Subject],
    table: RuleTable,
    refusals: Mapping[RootRelativePath, RefusedRecord] | None = None,
) -> tuple[SubjectReport, ...]:
    """Run the table's rules over each document, skill, resource and layout entry, and report each in the order given.

    Args:
        database: The revision the subjects are read from; its model decides which specifications govern each.
        subjects: The documents, skills, resources and layout entries to check; a document in no corpus the
            database's model holds is ungoverned for every facet a specification governs, and a layout
            entry is a symlink whose chain leaves the repository, as the database's model or a skill's resource
            listing records it.
        table: The rules the run enables, each with its severity.
        refusals: Docs paths the snapshot refused, whose diagnostics the caller reports; empty by default.

    Raises:
        DocumentReadError: If a document is missing from the snapshot; a decode failure is a diagnostic.
        SkillReadError: If a skill's `SKILL.md` is missing from the snapshot; a decode failure is a diagnostic.
        SkillResourceReadError: If a resource is missing from the snapshot; a decode failure is a diagnostic.
    """
    if refusals is None:
        refusals = {}
    reports: list[SubjectReport] = []
    for subject in subjects:
        match subject:
            case DocumentRef() as ref if isinstance(refusals.get(ref.path), RefusedRead):
                continue  # the unreadable-document report is already in the caller's reports
            case SkillLocation() as location if _is_refused_docs_path(location.file_resolves_to, refusals):
                reports.append(SkippedSubject(location.ref, (location.file_resolves_to,)))
            case SkillResourceLocation() as location if _is_refused_docs_path(location.resolves_to, refusals):
                reports.append(SkippedSubject(location.ref, (location.resolves_to,)))
            case RefusedSkillSubject(ref=ref, refused_at=path):
                reports.append(SkippedSubject(ref, (path,)))
            case DocumentRef() | SkillLocation():
                reports.append(_check_item(database, subject, table))
            case SkillResourceLocation():
                reports.append(check_skill_resource(database, subject, table))
            case OutsideSymlink():
                reports.append(check_layout_entry(subject, table))
            case _:
                assert_never(subject)
    return tuple(reports)


def _is_refused_docs_path(path: RootRelativePath, refusals: Mapping[RootRelativePath, RefusedRecord]) -> bool:
    """Whether a subject resolves to a refused path under `docs/`.

    Args:
        path: The resolved file path the subject depends on.
        refusals: Snapshot refusals keyed by their root-relative path.
    """
    return path.is_relative_to(DOCS_DIR) and refusals.get(path) is not None


def _check_item(database: Database, subject: DocumentRef | SkillLocation, table: RuleTable) -> SubjectReport:
    """Decode one document or skill entry, then judge it if it decoded and no failed layer governs it.

    The skip policy is the same for both kinds: it reads the item's governance and never which kind it is.

    Args:
        database: The revision the item is read from.
        subject: The document or skill entry to check.
        table: The rules the run enables.

    Raises:
        DocumentReadError: If the document is missing from the snapshot; a decode failure is a diagnostic.
        SkillReadError: If a skill's `SKILL.md` is missing from the snapshot; a decode failure is a diagnostic.
    """
    match subject:
        case DocumentRef():
            source = database.text(subject)
            governance = database.governance(subject)
        case SkillLocation():
            source = database.skill_text(subject)
            governance = database.item_governance(MarkdownItemRef(subject.ref.path))
        case _:
            assert_never(subject)
    match source:
        case Undecodable():
            return UndecodableSubject(source.ref, source.failure)
        case DocumentText() | SkillText():
            # Governance is a lookup in the model, never a rule, so a skipped item reads nothing else.
            if governance is not None:
                failed_layers = governance.failed_layers()
                if failed_layers:
                    # `SkippedSubject` requires a first path, so the first failed layer is split from the rest.
                    first, *others = failed_layers
                    return SkippedSubject(source.ref, (first.path, *(layer.path for layer in others)))
            return judge_item(database, source, table)
        case _:
            assert_never(source)
