"""Run checks over workspace subjects, applying failed-layer policy after decoding.

A failed governing layer suppresses meta-spec-gated rules for any decoded item, while `Always` and schema rules still
run. The suppressed parts appear as coverage. An item whose read was refused, or an item or skill alias whose docs
dependency was refused, is reported as skipped; the refusal itself is reported at its target.
"""

from collections.abc import Iterable, Mapping
from dataclasses import replace
from typing import assert_never

from lorecraft.core.path import RootRelativePath
from lorecraft.project.corpus import ReservedCorpusDirectory
from lorecraft.project.database import Database, ItemText, Undecodable
from lorecraft.project.item import ItemRef, ItemType, MetaSpecPart
from lorecraft.project.skill import OutsideSymlink, RefusedSkillAlias
from lorecraft.rules.report import CheckedItem, SkipCause, SkippedSubject, SubjectReport, UndecodableSubject
from lorecraft.rules.table import EnabledRule, QueriedItem, RuleTable
from lorecraft.vfs import RefusedRead, RefusedRecord

from .runner import ItemRuleLookup, check_layout_entry, judge_item

# A subject `check_subjects` dispatches: a document, a meta spec, a skill, a resource, a refused skill alias,
# or a layout entry. Each report holds its ref or the path an agent reaches the symlink by.
type CheckedSubject = ItemRef | OutsideSymlink | ReservedCorpusDirectory | RefusedSkillAlias


class _WithoutRepositoryMetaSpecRules(ItemRuleLookup):
    """A check run's view of the table when a repository layer failed."""

    def __init__(self, table: RuleTable, builtin_parts: frozenset[MetaSpecPart]) -> None:
        self._table = table
        self._builtin_parts = builtin_parts

    def item_rules(self, item_type: ItemType, part: MetaSpecPart | None) -> tuple[EnabledRule[QueriedItem], ...]:
        """Keep unconditional and builtin rules while hiding rules from failed repository layers."""
        if part is not None and part not in self._builtin_parts:
            return ()
        return self._table.item_rules(item_type, part)


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
        refusals: Snapshot paths the caller reports as refused reads or docs dependencies; empty by default.

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
                reports.append(SkippedSubject(ref, (path,), SkipCause.REFUSED_DEPENDENCY))
            case OutsideSymlink() | ReservedCorpusDirectory():
                reports.append(check_layout_entry(subject, database, table))
            case _:
                assert_never(subject)
    return tuple(reports)


def _is_refused_path(path: RootRelativePath, refusals: Mapping[RootRelativePath, RefusedRecord]) -> bool:
    """Whether a subject resolves to a refused read path.

    Args:
        path: The resolved file path the subject depends on.
        refusals: Snapshot refusals keyed by their root-relative path.
    """
    return isinstance(refusals.get(path), RefusedRead)


def _check_item(
    database: Database,
    item: ItemRef,
    table: RuleTable,
    refusals: Mapping[RootRelativePath, RefusedRecord],
) -> tuple[SubjectReport, ...]:
    """Decode one item and judge it, suppressing meta-spec gates when a governing layer failed.

    Every item type is decoded the same way, by its common reference. A missing file raises the item's read error;
    meta specs have no distinct missing-file error, so their item read error propagates. Failed layers suppress
    meta-spec gates for every governed item type but do not suppress `Always` or schema gates.

    Args:
        database: The revision the item is read from.
        item: The document, meta spec, skill or resource to check by its common reference.
        table: The rules the run enables.
        refusals: Paths in the snapshot the run could not read.

    Raises:
        ItemReadError: If the item is missing from the snapshot; a decode failure is a diagnostic.
    """
    descriptor = database.item_descriptor(item)
    if _is_refused_path(descriptor.read_location, refusals):
        return (SkippedSubject(item, (descriptor.read_location,), SkipCause.REFUSED_PATH),)
    source = database.item_text(item)
    match source:
        case Undecodable():
            return (UndecodableSubject(item, source.failure),)
        case ItemText():
            governance = database.item_governance(item)
            failed_layers = () if governance is None else governance.failed_layers()
            if failed_layers:
                return (_judge_after_failed_layer(database, source, table),)
            return (judge_item(database, source, table),)
        case _:
            assert_never(source)


def _judge_after_failed_layer(database: Database, source: ItemText, table: RuleTable) -> CheckedItem:
    """Keep the builtin floor while hiding failed repository layers, and report their parts as coverage."""
    builtin_parts = database.model().builtin_parts_for(source.descriptor.type)
    report = judge_item(database, source, _WithoutRepositoryMetaSpecRules(table, builtin_parts))
    suppressed = {
        part for part in MetaSpecPart if part not in builtin_parts and table.item_rules(source.descriptor.type, part)
    }
    ungoverned = suppressed | set(report.ungoverned)
    return replace(report, ungoverned=tuple(part for part in MetaSpecPart if part in ungoverned))
