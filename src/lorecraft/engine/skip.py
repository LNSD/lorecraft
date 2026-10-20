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
from lorecraft.project.item import ItemRef, ItemType, MetaSpecPart
from lorecraft.project.layout import DOCS_DIR
from lorecraft.project.skill import OutsideSymlink, RefusedSkillAlias
from lorecraft.rules.report import SkippedSubject, SkipReason, SubjectReport, UndecodableSubject
from lorecraft.rules.table import RuleTable
from lorecraft.vfs import RefusedRead, RefusedRecord

from .runner import check_layout_entry, judge_item

# A subject `check_subjects` dispatches: a document, a meta spec, a skill, a resource, a refused skill alias,
# or a layout entry. Each report holds its ref or the path an agent reaches the symlink by.
type CheckedSubject = ItemRef | OutsideSymlink | ReservedCorpusDirectory | RefusedSkillAlias


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
            case ItemRef() as ref:
                reports.extend(_check_item(database, ref, table, refusals))
            case RefusedSkillAlias(ref=ref, refused_at=path):
                reports.append(SkippedSubject(ref, (path,), SkipReason.REFUSED_PATH))
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
    database: Database,
    item: ItemRef,
    table: RuleTable,
    refusals: Mapping[RootRelativePath, RefusedRecord],
) -> tuple[SubjectReport, ...]:
    """Decode one item subject through the item queries, then judge it if it decoded and no failed layer skips it.

    Every item type is decoded the same way, by its common reference. A missing file is reported by the read error of
    its type; a meta spec has none, so it raises the item's own. A document is skipped when a failed layer
    governs it; a skill retains its Agent Skills checks. Resources have no corpus governance, and
    meta specs have no corpus governance.

    Args:
        database: The revision the item is read from.
        item: The document, meta spec, skill or resource to check by its common reference.
        table: The rules the run enables.
        refusals: Paths in the snapshot the run could not read.

    Raises:
        ItemReadError: If the item is missing from the snapshot; a decode failure is a diagnostic.
    """
    if isinstance(refusals.get(item.path), RefusedRead):
        return ()  # the unreadable-item report is already in the caller's reports
    descriptor = database.item_descriptor(item)
    if _is_refused_docs_path(descriptor.read_location, refusals):
        return (SkippedSubject(item, (descriptor.read_location,), SkipReason.REFUSED_PATH),)
    source = database.item_text(item)
    match source:
        case Undecodable():
            return (UndecodableSubject(item, source.failure),)
        case ItemText():
            match source.descriptor.type:
                case ItemType.DOCUMENT | ItemType.META_SPEC:
                    # Governance is a lookup in the model, never a rule, so a skipped item reads nothing else.
                    governance = database.item_governance(item)
                    if governance is not None:
                        failed_layers = governance.failed_layers()
                        if failed_layers:
                            # `SkippedSubject` requires a first path, so the first failed layer is split from the rest.
                            first, *others = failed_layers
                            return (
                                SkippedSubject(
                                    item,
                                    (first.path, *(layer.path for layer in others)),
                                    SkipReason.FAILED_STRUCTURE,
                                ),
                            )
                case ItemType.SKILL_ENTRYPOINT:
                    governance = database.item_governance(item)
                    if governance is not None and governance.failed_layers():
                        table = table.without_item_meta_spec_gates(
                            ItemType.SKILL_ENTRYPOINT,
                            frozenset({MetaSpecPart.STRUCTURE, MetaSpecPart.OUTLINE, MetaSpecPart.BUDGET}),
                        )
                case ItemType.SKILL_RESOURCE:
                    pass  # resources have no corpus governance
                case _:
                    assert_never(source.descriptor.type)
            return (judge_item(database, source, table),)
        case _:
            assert_never(source)
