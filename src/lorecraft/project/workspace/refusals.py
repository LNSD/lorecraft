"""Which of the refusals a snapshot kept the model reports as load failures, and which nothing reports.

A scan given a declaration keeps every directory it cannot list, every entry on a followed chain it cannot inspect,
and every structure file it cannot read, instead of stopping at it. The loader turns the ones it meets into load
failures. A directory no meta spec names, or one inside a skill that nothing lists, is never met: left alone, its
refusal would pass unreported where the scan used to stop. This module finds those, and raises the first as the
scan raised it, so that the command stops as it did. One refusal is accepted without a failure: a refused read of a
legacy `<name>.structure.json` that a `<name>.spec.json` shadows, since that file governs nothing.
"""

from collections.abc import Mapping
from typing import assert_never

from lorecraft.core.error import Error
from lorecraft.core.path import PathComponent, RootRelativePath
from lorecraft.project.layout import SPECS_DIR
from lorecraft.project.schemas import SpecFileType, spec_filename
from lorecraft.project.schemas.structure_failure import (
    AdjacentAnyRuns,
    CyclicFrontmatterSchemaRef,
    EmptyStructureSpec,
    ForbiddenOutlineSections,
    ForeignFrontmatterDialect,
    IdentifiedFrontmatterSchema,
    InvalidFrontmatterSchema,
    InvalidTitlePattern,
    RepeatedForbiddenSections,
    RepeatedOutlineSections,
    UndecodableStructureSpec,
    UnresolvableFrontmatterSchemaRef,
    UntypedFrontmatterSchema,
)
from lorecraft.vfs import OsRefusal, RefusedInspect, RefusedListing, RefusedRead, RefusedRecord

from .failure import (
    NonUtf8StructureFile,
    UninspectableSkillEntry,
    UninspectableSkillFile,
    UninspectableSkillsDirectory,
    UnlistableCorpusDirectory,
    UnlistableDirectory,
    UnlistableSkillDirectory,
    UnlistableSkillsDirectory,
    UnreadableStructureFile,
    UnrecordedStructureFile,
    UnresolvableSkillEntry,
    UnresolvableSkillFile,
    UnresolvableSkillsDirectory,
)
from .model import CorpusSpec, NamespaceSpec, WorkspaceModel


class UnreportedDirListError(Error):
    """A directory the scan could not list, which no load failure of the model reports.

    Attributes:
        path: The root-relative directory that could not be listed.
        refusal: Why the operating system refused the listing.
    """

    path: RootRelativePath
    refusal: OsRefusal

    def __init__(self, path: RootRelativePath, refusal: OsRefusal) -> None:
        self.path = path
        self.refusal = refusal
        super().__init__(f'cannot snapshot directory {path}: {refusal}')


class UnreportedFileReadError(Error):
    """A file the scan could not read, which no load failure of the model reports.

    Attributes:
        path: The root-relative file that could not be read.
        refusal: Why the operating system refused the read.
    """

    path: RootRelativePath
    refusal: OsRefusal

    def __init__(self, path: RootRelativePath, refusal: OsRefusal) -> None:
        self.path = path
        self.refusal = refusal
        super().__init__(f'cannot snapshot file {path}: {refusal}')


class UnreportedEntryInspectError(Error):
    """An entry the scan could not inspect, which no load failure of the model reports.

    Attributes:
        path: The root-relative entry that could not be inspected.
        refusal: Why the operating system refused the inspection.
    """

    path: RootRelativePath
    refusal: OsRefusal

    def __init__(self, path: RootRelativePath, refusal: OsRefusal) -> None:
        self.path = path
        self.refusal = refusal
        super().__init__(f'cannot snapshot entry {path}: {refusal}')


def _shadowed_legacy_files(model: WorkspaceModel) -> set[RootRelativePath]:
    """The legacy `<name>.structure.json` paths a `<name>.spec.json` of the model shadows.

    The loader neither lists nor reads such a file, so it can be refused without any load failure reporting it; the
    refusal is of a file that governs nothing.

    Args:
        model: The workspace model, whose specification files are listed without the shadowed ones.
    """
    shadowed: set[RootRelativePath] = set()
    for corpus in model.sorted_corpora:
        specs: list[CorpusSpec | NamespaceSpec] = [corpus.corpus_spec, *corpus.namespace_specs]
        for spec in specs:
            spec_json = SPECS_DIR / PathComponent.parse(spec_filename(spec.name, SpecFileType.SPEC))
            if spec_json in spec.files:
                legacy_name = spec_filename(spec.name, SpecFileType.LEGACY_STRUCTURE)
                shadowed.add(SPECS_DIR / PathComponent.parse(legacy_name))
    return shadowed


def unreported_refusals(
    refusals: Mapping[RootRelativePath, RefusedRecord], model: WorkspaceModel
) -> dict[RootRelativePath, RefusedRecord]:
    """The refusals no load failure of the model reports, keyed by path, in the order `refusals` is given.

    A refused listing is reported by the failure of the directory that could not be listed, a refused read by the
    failure of the structure file, and a refused inspection by the failure of the skills directory, skill entry or
    `SKILL.md` that names the entry it stopped at. A refused read of a legacy `<name>.structure.json` that a
    `<name>.spec.json` shadows is accepted as reported, because that file governs nothing.

    Args:
        refusals: Every refusal the snapshot kept, as the database answers them.
        model: The workspace model loaded from that snapshot.
    """
    listings: set[RootRelativePath] = set()
    reads: set[RootRelativePath] = set()
    inspections: set[RootRelativePath] = set()
    for failure in model.load_failures:
        condition = failure.condition
        match condition:
            case UnlistableDirectory() | UnlistableCorpusDirectory():
                listings.add(failure.path)
            case UnlistableSkillsDirectory(failed_at=failed_at) | UnlistableSkillDirectory(failed_at=failed_at):
                listings.add(failed_at)
            case UnreadableStructureFile():
                reads.add(failure.path)
            case (
                UninspectableSkillsDirectory(failed_at=failed_at)
                | UninspectableSkillEntry(failed_at=failed_at)
                | UninspectableSkillFile(failed_at=failed_at)
            ):
                inspections.add(failed_at)
            case (
                UnrecordedStructureFile()
                | NonUtf8StructureFile()
                | UndecodableStructureSpec()
                | EmptyStructureSpec()
                | RepeatedOutlineSections()
                | RepeatedForbiddenSections()
                | ForbiddenOutlineSections()
                | AdjacentAnyRuns()
                | InvalidTitlePattern()
                | InvalidFrontmatterSchema()
                | IdentifiedFrontmatterSchema()
                | ForeignFrontmatterDialect()
                | UnresolvableFrontmatterSchemaRef()
                | CyclicFrontmatterSchemaRef()
                | UntypedFrontmatterSchema()
                | UnresolvableSkillsDirectory()
                | UnresolvableSkillEntry()
                | UnresolvableSkillFile()
            ):
                pass  # a structure file's content failed, or a lookup the disk refused: no snapshot refusal
            case _:
                assert_never(condition)

    shadowed_legacy_files = _shadowed_legacy_files(model)
    unreported: dict[RootRelativePath, RefusedRecord] = {}
    for path, refused in refusals.items():
        match refused:
            case RefusedListing():
                is_reported = path in listings
            case RefusedRead():
                is_reported = path in reads or path in shadowed_legacy_files
            case RefusedInspect():
                is_reported = path in inspections
            case _:
                assert_never(refused)
        if not is_reported:
            unreported[path] = refused
    return unreported


def reject_unreported_refusals(refusals: Mapping[RootRelativePath, RefusedRecord], model: WorkspaceModel) -> None:
    """Raise the first refusal no load failure of the model reports, worded as a refusal that stopped the scan.

    Args:
        refusals: Every refusal the snapshot kept, in path order, as the database answers them.
        model: The workspace model loaded from that snapshot.

    Raises:
        UnreportedDirListError: If the first such refusal is of a directory listing.
        UnreportedFileReadError: If the first such refusal is of a file read.
        UnreportedEntryInspectError: If the first such refusal is of an entry inspection.
    """
    for path, refused in unreported_refusals(refusals, model).items():
        match refused:
            case RefusedListing():
                raise UnreportedDirListError(path, refused.refusal)
            case RefusedRead():
                raise UnreportedFileReadError(path, refused.refusal)
            case RefusedInspect():
                raise UnreportedEntryInspectError(path, refused.refusal)
            case _:
                assert_never(refused)
