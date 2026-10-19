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
from lorecraft.project.item import ItemKind, ItemRef, MetaSpecPart
from lorecraft.project.layout import DOCS_DIR
from lorecraft.project.skill import (
    OutsideSymlink,
    RefusedSkillAlias,
    SkillLocation,
    SkillResourceLocation,
)
from lorecraft.rules.report import SkippedSubject, SkipReason, SubjectReport, UndecodableSubject
from lorecraft.rules.table import RuleTable
from lorecraft.vfs import RefusedRead, RefusedRecord

from .runner import check_layout_entry, judge_item

# A subject `check_subjects` dispatches: a document, a meta spec, a skill, a resource, a refused skill alias,
# or a layout entry. Each report holds its ref or the path an agent reaches the symlink by.
type CheckedSubject = (
    ItemRef | SkillLocation | SkillResourceLocation | OutsideSymlink | ReservedCorpusDirectory | RefusedSkillAlias
)


def check_subjects(
    database: Database,
    subjects: Iterable[CheckedSubject],
    table: RuleTable,
    refusals: Mapping[RootRelativePath, RefusedRecord] | None = None,
) -> tuple[SubjectReport, ...]:
    """Run the table's rules over each document, meta spec, skill, resource and layout entry, and report each.

    Args:
        database: The revision the subjects are read from; its model decides which meta specs govern each.
        subjects: The documents, meta specs, skills, resources and layout entries to check; a document in no
            corpus the database's model holds is ungoverned for every gate a meta spec governs, and a layout
            entry is a symlink whose chain leaves the repository or a directory named like a reserved corpus, as the
            database's model or a skill's resource listing records it.
        table: The rules the run enables, each with its severity.
        refusals: Docs paths the snapshot refused, whose diagnostics the caller reports; empty by default.

    Raises:
        ItemReadError: If an item is missing from the snapshot; a decode failure is a diagnostic.
    """
    if refusals is None:
        refusals = {}
    reports: list[SubjectReport] = []
    for subject in subjects:
        match subject:
            case ItemRef() as ref if isinstance(refusals.get(ref.path), RefusedRead):
                continue  # the unreadable-document report is already in the caller's reports
            case SkillLocation() as location if _is_refused_docs_path(location.file_resolves_to, refusals):
                reports.append(
                    SkippedSubject(ItemRef(location.ref.path), (location.file_resolves_to,), SkipReason.REFUSED_PATH)
                )
            case SkillResourceLocation() as location if _is_refused_docs_path(location.resolves_to, refusals):
                reports.append(
                    SkippedSubject(ItemRef(location.ref.path), (location.resolves_to,), SkipReason.REFUSED_PATH)
                )
            case RefusedSkillAlias(ref=ref, refused_at=path):
                reports.append(SkippedSubject(ref, (path,), SkipReason.REFUSED_PATH))
            case ItemRef() | SkillLocation() | SkillResourceLocation():
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
    database: Database, subject: ItemRef | SkillLocation | SkillResourceLocation, table: RuleTable
) -> SubjectReport:
    """Decode one item subject through the item queries, then judge it if it decoded and no failed layer skips it.

    Every item kind is decoded the same way, by its common reference. A missing file is reported by the read error of
    its kind; a meta spec has none, so it raises the item's own. A document is skipped when a failed layer
    governs it; a skill retains its Agent Skills checks. Resources have no corpus governance, and
    meta specs have no corpus governance.

    Args:
        database: The revision the item is read from.
        subject: The document, meta spec, skill or resource to check.
        table: The rules the run enables.

    Raises:
        ItemReadError: If the item is missing from the snapshot; a decode failure is a diagnostic.
    """
    match subject:
        case ItemRef():
            item = subject
        case SkillLocation():
            item = ItemRef(subject.ref.path)
        case SkillResourceLocation():
            item = ItemRef(subject.ref.path)
        case _:
            assert_never(subject)
    source = database.item_text(item)
    match source:
        case Undecodable():
            return UndecodableSubject(item, source.failure)
        case ItemText():
            match source.descriptor.kind:
                case ItemKind.DOCUMENT:
                    # Governance is a lookup in the model, never a rule, so a skipped item reads nothing else.
                    governance = database.item_governance(item)
                    if governance is not None:
                        failed_layers = governance.failed_layers()
                        if failed_layers:
                            # `SkippedSubject` requires a first path, so the first failed layer is split from the rest.
                            first, *others = failed_layers
                            return SkippedSubject(
                                item,
                                (first.path, *(layer.path for layer in others)),
                                SkipReason.FAILED_STRUCTURE,
                            )
                case ItemKind.SKILL_ENTRYPOINT:
                    governance = database.item_governance(item)
                    if governance is not None and governance.failed_layers():
                        table = table.without_item_meta_spec_gates(
                            ItemKind.SKILL_ENTRYPOINT,
                            frozenset({MetaSpecPart.STRUCTURE, MetaSpecPart.OUTLINE, MetaSpecPart.BUDGET}),
                        )
                case ItemKind.META_SPEC | ItemKind.SKILL_RESOURCE:
                    pass  # neither kind is skipped by a failed corpus layer
                case _:
                    assert_never(source.descriptor.kind)
            return judge_item(database, source, table)
        case _:
            assert_never(source)
