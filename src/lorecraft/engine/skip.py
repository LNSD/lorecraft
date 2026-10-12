"""The check run's entry point: the rules over each subject, as `lorecraft check` runs them.

The check run is one mode of the engine. This module is that mode's own entry point over the shared runner: it matches
on each subject kind and calls the function of `lorecraft.engine.runner` that judges it, so the policy of the run is
here and never in the runner. A mode that treats a document a failed layer governs differently is an entry point of its
own beside this one, not a parameter of this function.

The check run's policy for a document a failed layer governs is to skip it: the layers of a meta spec apply by
conjunction, so a document cannot be called clean from the layers that loaded. The document is decoded first, so a file
that does not decode is reported as it always is; a decoded one that a failed layer governs gets no rule and is
reported as skipped, with the structure file of each failed layer.
"""

from collections.abc import Iterable
from typing import assert_never

from lorecraft.project.database import Database, DocumentText, Undecodable
from lorecraft.project.document import DocumentRef
from lorecraft.project.skill import OutsideSymlink, SkillLocation, SkillResourceLocation
from lorecraft.rules.report import SkippedSubject, SubjectReport, UndecodableSubject
from lorecraft.rules.table import RuleTable

from .runner import Subject, check_layout_entry, check_skill, check_skill_resource, judge_document


def check_subjects(database: Database, subjects: Iterable[Subject], table: RuleTable) -> tuple[SubjectReport, ...]:
    """Run the table's rules over each document, skill, resource and layout entry, and report each in the order given.

    Args:
        database: The revision the subjects are read from; its model decides which specifications govern each.
        subjects: The documents, skills, resources and layout entries to check; a document in no corpus the
            database's model holds is ungoverned for every facet a specification governs, and a layout
            entry is a symlink whose chain leaves the repository, as the database's model or a skill's resource
            listing records it.
        table: The rules the run enables, each with its severity.

    Raises:
        DocumentReadError: If a document is missing from the snapshot; a decode failure is a diagnostic.
        SkillReadError: If a skill's `SKILL.md` is missing from the snapshot; a decode failure is a diagnostic.
        SkillResourceReadError: If a resource is missing from the snapshot; a decode failure is a diagnostic.
    """
    reports: list[SubjectReport] = []
    for subject in subjects:
        match subject:
            case DocumentRef():
                reports.append(_check_document(database, subject, table))
            case SkillLocation():
                reports.append(check_skill(database, subject, table))
            case SkillResourceLocation():
                reports.append(check_skill_resource(database, subject, table))
            case OutsideSymlink():
                reports.append(check_layout_entry(subject, table))
            case _:
                assert_never(subject)
    return tuple(reports)


def _check_document(database: Database, ref: DocumentRef, table: RuleTable) -> SubjectReport:
    """Decode one document, then run the table's rules over it if it decoded and no failed layer governs it.

    Args:
        database: The revision the document is read from.
        ref: The document to check.
        table: The rules the run enables.

    Raises:
        DocumentReadError: If the document is missing from the snapshot; a decode failure is a diagnostic.
    """
    source = database.text(ref)
    match source:
        case Undecodable():
            return UndecodableSubject(ref, source.failure)
        case DocumentText():
            # Governance is a lookup in the model, never a rule, so a skipped document reads nothing else.
            governance = database.governance(ref)
            if governance is not None:
                failed_layers = governance.failed_layers()
                if failed_layers:
                    return SkippedSubject(ref, tuple(layer.path for layer in failed_layers))
            return judge_document(database, source, table)
        case _:
            assert_never(source)
