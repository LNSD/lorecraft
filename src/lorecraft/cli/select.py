"""Choose the subjects a run of the rules engine checks: the whole workspace one revision holds.

A subject is a document, a skill, a resource of a skill, or a symlink of the skill layout whose chain leaves the
repository. The workspace is every one of them the model lists: each document, each skill whole, which is its
`SKILL.md`, every resource its listing gives and every symlink inside it that leads outside, and each skills
directory, entry or entry's `SKILL.md` that leads outside. The subjects are sorted by the path each is reported at,
so a run reports the same revision in the same order however the model or a listing orders them.
"""

from typing import assert_never

from lorecraft.checks import Subject
from lorecraft.core.path import RootRelativePath
from lorecraft.project.database import Database
from lorecraft.project.document import DocumentRef
from lorecraft.project.skill import OutsideSymlink, SkillLocation, SkillResourceLocation


def select_workspace(database: Database) -> tuple[Subject, ...]:
    """Every subject of the workspace, each once, sorted by the path it is reported at, compared by code point.

    Nothing is deduplicated here, since nothing can repeat: the model lists each skill and each symlink leading
    outside once, a listing's resources and symlinks sit under its own skill's path, and the model's symlinks are
    the skills directories, entries and `SKILL.md` files, never one inside a skill.

    Args:
        database: The revision whose model lists the documents, the skills and the symlinks leading outside, and
            whose resource listing of each skill gives its resources and the symlinks inside it.

    Raises:
        DirListError: If the model is not loaded yet and the specification directory or docs/ cannot be listed.
        CorpusListError: If the model is not loaded yet and a corpus directory cannot be listed.
        StructureSchemaReadError: If the model is not loaded yet and a structure specification cannot be read.
        StructureSpecDecodeError: If the model is not loaded yet and a structure specification is not JSON in the
            dialect's shape.
        EmptyStructureSpecError: If the model is not loaded yet and a structure specification states no rule.
        RepeatedOutlineSectionError: If the model is not loaded yet and an outline names a section twice.
        RepeatedForbiddenSectionError: If the model is not loaded yet and a specification forbids a section twice.
        ForbiddenOutlineSectionError: If the model is not loaded yet and a specification forbids a section its
            outline names.
        AdjacentAnyRunsError: If the model is not loaded yet and an outline places two `any` runs side by side.
        InvalidTitlePatternError: If the model is not loaded yet and a title's pattern does not compile.
        InvalidFrontmatterSchemaError: If the model is not loaded yet and a frontmatter schema is rejected by the
            meta-schema.
        FrontmatterSchemaIdError: If the model is not loaded yet and a schema in a frontmatter schema carries `$id`.
        ForeignFrontmatterDialectError: If the model is not loaded yet and a schema in a frontmatter schema names
            another dialect.
        UntypedFrontmatterSchemaError: If the model is not loaded yet and a frontmatter schema's root does not state
            an object.
        DirResolveError: If the model is not loaded yet and a skills directory cannot be resolved.
        EntryInspectError: If the model is not loaded yet and an entry on the way to a skills directory cannot be
            inspected, or a link's target read, while looking for where it leaves the repository.
        SkillsDirListError: If the model is not loaded yet and a skills directory cannot be listed.
        SkillEntryResolveError: If the model is not loaded yet and a symlinked skill entry cannot be resolved.
        SkillDirListError: If the model is not loaded yet and a skill directory cannot be listed.
        SkillFileResolveError: If the model is not loaded yet and a symlinked SKILL.md cannot be resolved.
        SkillResourcesListError: If a directory inside a skill cannot be listed.
        SkillResourcesSymlinkResolveError: If a symlink inside a skill cannot be resolved.
    """
    model = database.model()
    subjects: list[Subject] = []
    subjects.extend(model.documents())
    for location in model.skill_locations:
        subjects.append(location)
        listing = database.skill_resources(location)
        subjects.extend(listing.resources)
        subjects.extend(listing.outside_symlinks)
    subjects.extend(model.outside_symlinks)

    # Compared as POSIX strings, by code point and never by locale, as the diagnostics they report are ordered.
    return tuple(sorted(subjects, key=lambda subject: str(_report_path(subject))))


def _report_path(subject: Subject) -> RootRelativePath:
    """The path a subject's report is filed at: a skill's is its `SKILL.md`, a symlink's where an agent reaches it.

    Args:
        subject: The document, skill, resource or symlink whose report is placed.
    """
    match subject:
        case DocumentRef():
            return subject.path
        case SkillLocation():
            return subject.ref.path
        case SkillResourceLocation():
            return subject.ref.path
        case OutsideSymlink():
            return subject.path
        case _:
            assert_never(subject)
