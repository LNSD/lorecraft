"""Run checks over workspace subjects, skipping files whose required input was refused.

A document governed by a meta spec that failed to load cannot be called clean from only the layers that loaded. It is
decoded first, and a decoded document is skipped with the failed structure paths. A skill still receives its
Agent Skills checks when a corpus layer fails; rules that depend on the corpus are suppressed by the runner. A skill
or resource whose resolved docs target was refused is skipped; the refusal itself is reported at its target.
"""

from collections.abc import Iterable, Mapping
from typing import assert_never

from lorecraft.core.path import RootRelativePath
from lorecraft.project.corpus import ReservedCorpusDirectory
from lorecraft.project.database import Database, ItemText, Undecodable
from lorecraft.project.document import DocumentReadError, DocumentRef, MetaSpecRef
from lorecraft.project.item import ItemReadError, ItemRef
from lorecraft.project.layout import DOCS_DIR
from lorecraft.project.skill import (
    OutsideSymlink,
    RefusedSkillAlias,
    SkillLocation,
    SkillReadError,
    SkillRef,
    SkillResourceLocation,
    SkillResourceReadError,
    SkillResourceRef,
)
from lorecraft.rules.report import SkippedSubject, SubjectReport, UndecodableSubject
from lorecraft.rules.table import RuleTable
from lorecraft.vfs import RefusedRead, RefusedRecord

from .runner import check_layout_entry, judge_item

# A subject `check_subjects` dispatches: a document, a meta specification, a skill, a resource, a refused skill alias,
# or a layout entry. Each report holds its ref or the path an agent reaches the symlink by.
type CheckedSubject = (
    DocumentRef
    | MetaSpecRef
    | SkillLocation
    | SkillResourceLocation
    | OutsideSymlink
    | ReservedCorpusDirectory
    | RefusedSkillAlias
)

type ReportedRef = DocumentRef | MetaSpecRef | SkillRef | SkillResourceRef


def check_subjects(
    database: Database,
    subjects: Iterable[CheckedSubject],
    table: RuleTable,
    refusals: Mapping[RootRelativePath, RefusedRecord] | None = None,
) -> tuple[SubjectReport, ...]:
    """Run the table's rules over each document, specification, skill, resource and layout entry, and report each.

    Args:
        database: The revision the subjects are read from; its model decides which specifications govern each.
        subjects: The documents, specifications, skills, resources and layout entries to check; a document in no
            corpus the database's model holds is ungoverned for every gate a specification governs, and a layout
            entry is a symlink whose chain leaves the repository or a directory named like a reserved corpus, as the
            database's model or a skill's resource listing records it.
        table: The rules the run enables, each with its severity.
        refusals: Docs paths the snapshot refused, whose diagnostics the caller reports; empty by default.

    Raises:
        DocumentReadError: If a document is missing from the snapshot; a decode failure is a diagnostic.
        SkillReadError: If a skill's `SKILL.md` is missing from the snapshot; a decode failure is a diagnostic.
        SkillResourceReadError: If a resource is missing from the snapshot; a decode failure is a diagnostic.
        ItemReadError: If a specification is missing from the snapshot; a decode failure is a diagnostic.
    """
    if refusals is None:
        refusals = {}
    reports: list[SubjectReport] = []
    for subject in subjects:
        match subject:
            case DocumentRef() | MetaSpecRef() as ref if isinstance(refusals.get(ref.path), RefusedRead):
                continue  # the unreadable-document report is already in the caller's reports
            case SkillLocation() as location if _is_refused_docs_path(location.file_resolves_to, refusals):
                reports.append(SkippedSubject(location.ref, (location.file_resolves_to,)))
            case SkillResourceLocation() as location if _is_refused_docs_path(location.resolves_to, refusals):
                reports.append(SkippedSubject(location.ref, (location.resolves_to,)))
            case RefusedSkillAlias(ref=ref, refused_at=path):
                reports.append(SkippedSubject(ref, (path,)))
            case DocumentRef() | MetaSpecRef() | SkillLocation() | SkillResourceLocation():
                reports.append(_check_item(database, subject, table))
            case OutsideSymlink() | ReservedCorpusDirectory():
                reports.append(check_layout_entry(subject, database, table))
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


def _check_item(
    database: Database, subject: DocumentRef | MetaSpecRef | SkillLocation | SkillResourceLocation, table: RuleTable
) -> SubjectReport:
    """Decode one item subject through the item queries, then judge it if it decoded and no failed layer skips it.

    Every item kind is decoded the same way, by its common reference. A missing file is reported by the read error of
    its kind; a specification has none, so it raises the item's own. A document is skipped when a failed layer
    governs it; a skill retains its Agent Skills checks. Resources have no corpus governance, and
    specifications are governed by the package.

    Args:
        database: The revision the item is read from.
        subject: The document, specification, skill or resource to check.
        table: The rules the run enables.

    Raises:
        DocumentReadError: If the document is missing from the snapshot; a decode failure is a diagnostic.
        SkillReadError: If a skill's `SKILL.md` is missing from the snapshot; a decode failure is a diagnostic.
        SkillResourceReadError: If a resource is missing from the snapshot; a decode failure is a diagnostic.
        ItemReadError: If a specification is missing from the snapshot; a decode failure is a diagnostic.
    """
    match subject:
        case DocumentRef() | MetaSpecRef():
            ref: ReportedRef = subject
            item = ItemRef(subject.path)
        case SkillLocation():
            ref = subject.ref
            item = ItemRef(ref.path)
        case SkillResourceLocation():
            ref = subject.ref
            item = database.resource_item(subject)
        case _:
            assert_never(subject)
    try:
        source = database.item_text(item)
    except ItemReadError as exc:
        # The command reports a missing file by the error of its kind.
        match ref:
            case DocumentRef():
                raise DocumentReadError(ref, source=exc.source) from exc
            case SkillRef():
                raise SkillReadError(ref, source=exc.source) from exc
            case SkillResourceRef():
                raise SkillResourceReadError(ref, source=exc.source) from exc
            case MetaSpecRef():
                raise
            case _:
                assert_never(ref)
    match source:
        case Undecodable():
            return UndecodableSubject(ref, source.failure)
        case ItemText():
            match ref:
                case DocumentRef():
                    # Governance is a lookup in the model, never a rule, so a skipped item reads nothing else.
                    governance = database.item_governance(item)
                    if governance is not None:
                        failed_layers = governance.failed_layers()
                        if failed_layers:
                            # `SkippedSubject` requires a first path, so the first failed layer is split from the rest.
                            first, *others = failed_layers
                            return SkippedSubject(ref, (first.path, *(layer.path for layer in others)))
                case SkillRef():
                    pass  # the runner suppresses corpus rules but retains the Agent Skills floor
                case MetaSpecRef() | SkillResourceRef():
                    pass  # specs are package governed; resources have no corpus governance
                case _:
                    assert_never(ref)
            return judge_item(database, source, table)
        case _:
            assert_never(source)
