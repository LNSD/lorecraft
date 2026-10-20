"""Choose the subjects a run of the rules engine checks: the whole workspace one revision holds.

A subject is a document, a spec, a skill, a resource of a skill, a refused skill alias, or a layout
entry: a symlink of the skill layout whose chain leaves the repository, or a directory under `docs/` named like a
reserved corpus. The workspace is every one of them the model or a skill's resource listing gives: each document, each
spec, each skill whole, which is its `SKILL.md`, every resource and refused alias, every symlink that
leads outside and every such directory. The subjects are sorted by the path each is reported at, so a run reports the
same revision in the same order however the model or a listing orders them.
"""

from typing import assert_never

from lorecraft.core.path import RootRelativePath
from lorecraft.engine import CheckedSubject
from lorecraft.project.corpus import ReservedCorpusDirectory
from lorecraft.project.database import Database
from lorecraft.project.item import ItemRef
from lorecraft.project.skill import OutsideSymlink, RefusedSkillAlias


def select_workspace(database: Database) -> tuple[CheckedSubject, ...]:
    """Every subject of the workspace, each once, sorted by its report path, compared by code point.

    Nothing is deduplicated here, since nothing can repeat: the model lists each skill, each symlink leading outside
    and each reserved-corpus directory once, a listing's resources and aliases sit under its own skill's path, and the
    model's symlinks are the skills directories, entries and `SKILL.md` files, never one inside a skill.

    Args:
        database: The revision whose model lists the documents, the specs, the skills, the symlinks
            leading outside and the reserved-corpus directories, and whose resource listing of each skill gives its
            resources, aliases and symlinks inside it.
    """
    model = database.model()
    subjects: list[CheckedSubject] = []
    subjects.extend(ItemRef(ref.path) for ref in model.documents())
    subjects.extend(ItemRef(ref.path) for ref in model.specifications())
    for location in model.sorted_skill_locations:
        subjects.append(ItemRef(location.ref.path))
        listing = database.skill_resources(location)
        subjects.extend(ItemRef(resource.ref.path) for resource in listing.resources)
        subjects.extend(listing.outside_symlinks)
        subjects.extend(listing.refused_aliases)
    subjects.extend(model.sorted_outside_symlinks)
    subjects.extend(model.sorted_overlapping_directories)

    # Compared as POSIX strings, by code point and never by locale, as the diagnostics they report are ordered.
    return tuple(sorted(subjects, key=lambda subject: str(_report_path(subject))))


def _report_path(subject: CheckedSubject) -> RootRelativePath:
    """The path a subject's report is filed at: an item or layout entry's path.

    Args:
        subject: The item or layout entry whose report is placed.
    """
    match subject:
        case ItemRef():
            return subject.path
        case RefusedSkillAlias():
            return subject.ref.path
        case OutsideSymlink() | ReservedCorpusDirectory():
            return subject.path
        case _:
            assert_never(subject)
