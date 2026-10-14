"""The load failures the workspace model records: what could not be read or used while the model was built.

The loader reads the declaration unit by unit: a structure file, a corpus directory, a skills directory, a skill
entry, a skill's `SKILL.md`. A unit that fails is not raised: it is recorded, as one of the frozen records here, and
the loader goes on with the next unit (adr-015).

A record holds the facts the error it stands for carried, the path, the operating system's refusal or the decoder's
problems, and never the foreign exception that error wrapped, so it is plain data: it compares by value and a result
that holds one can persist (adr-005). There is one record type per condition, and the conditions are two closed
unions, so a reader that matches a failure is checked exhaustive.

Records name no code, no severity and no wording: what a failure becomes for a reader is decided by the command that
reads the model.
"""

from dataclasses import dataclass

from lorecraft.core.path import RootRelativePath
from lorecraft.project.corpus import CorpusName
from lorecraft.project.schemas.name import SpecName
from lorecraft.project.schemas.structure_failure import StructureSpecFailure
from lorecraft.vfs import OsRefusal, Utf8Failure

# The conditions of a structure file, which stands in its meta spec layer as a `FailedStructure`.


@dataclass(frozen=True, slots=True)
class UnreadableStructureFile:
    """The structure file exists in the listing but the operating system refused to read it.

    Attributes:
        name: The specification name whose structure file was read.
        refusal: Why the operating system refused the read.
    """

    name: SpecName
    refusal: OsRefusal


@dataclass(frozen=True, slots=True)
class UnrecordedStructureFile:
    """The structure file is no regular file the snapshot recorded, so a read of it answers like a missing file.

    Attributes:
        name: The specification name whose structure file was read.
    """

    name: SpecName


@dataclass(frozen=True, slots=True)
class NonUtf8StructureFile:
    """The structure file's bytes are not UTF-8, so it has no text to read.

    Attributes:
        failure: Where the file's bytes first stop being UTF-8, and why.
    """

    failure: Utf8Failure


# Every condition a structure file fails with.
type StructureLoadFailure = (
    UnreadableStructureFile | UnrecordedStructureFile | NonUtf8StructureFile | StructureSpecFailure
)


@dataclass(frozen=True, slots=True)
class FailedStructure:
    """A structure file that could not be read or used; it stands in the layer where its structure would.

    Attributes:
        path: Root-relative path of the structure file.
        failure: The condition it failed with.
    """

    path: RootRelativePath
    failure: StructureLoadFailure


# The conditions of the other units, which only the model's list of failures holds.


@dataclass(frozen=True, slots=True)
class UnlistableDirectory:
    """`docs/` or `docs/__meta__/` exists but cannot be listed, so no corpus and no meta spec is known from it.

    Attributes:
        refusal: Why the operating system refused the listing.
    """

    refusal: OsRefusal


@dataclass(frozen=True, slots=True)
class UnlistableCorpusDirectory:
    """A corpus directory exists but cannot be listed, so the corpus holds no document.

    Attributes:
        corpus: The corpus whose documents were being listed.
        refusal: Why the operating system refused the listing.
    """

    corpus: CorpusName
    refusal: OsRefusal


@dataclass(frozen=True, slots=True)
class UnresolvableSkillsDirectory:
    """The operating system refused a lookup on the way to a skills directory an agent declares.

    Attributes:
        refusal: Why the operating system refused the lookup.
    """

    refusal: OsRefusal


@dataclass(frozen=True, slots=True)
class UninspectableSkillsDirectory:
    """An entry on the way to a skills directory cannot be inspected, or a link's target read.

    Attributes:
        failed_at: The entry that could not be inspected, which may be one on the way to the skills directory.
        refusal: Why the operating system refused the inspection.
    """

    failed_at: RootRelativePath
    refusal: OsRefusal


@dataclass(frozen=True, slots=True)
class UnlistableSkillsDirectory:
    """A skills directory exists but cannot be listed.

    Attributes:
        failed_at: The resolved directory that could not be listed, which the declared one may be a link to.
        refusal: Why the operating system refused the listing.
    """

    failed_at: RootRelativePath
    refusal: OsRefusal


@dataclass(frozen=True, slots=True)
class UnresolvableSkillEntry:
    """The operating system refused a lookup while a symlinked skill entry was followed.

    Attributes:
        refusal: Why the operating system refused the lookup.
    """

    refusal: OsRefusal


@dataclass(frozen=True, slots=True)
class UninspectableSkillEntry:
    """A symlinked skill entry leads to no directory, and where its chain goes could not be inspected.

    Attributes:
        failed_at: The entry that could not be inspected, which may be one on the way.
        refusal: Why the operating system refused the inspection.
    """

    failed_at: RootRelativePath
    refusal: OsRefusal


@dataclass(frozen=True, slots=True)
class UnlistableSkillDirectory:
    """A skill's directory exists but cannot be listed to look for its `SKILL.md`.

    Attributes:
        failed_at: The resolved directory that could not be listed, which the skill entry may be a link to.
        refusal: Why the operating system refused the listing.
    """

    failed_at: RootRelativePath
    refusal: OsRefusal


@dataclass(frozen=True, slots=True)
class UnresolvableSkillFile:
    """The operating system refused a lookup while a symlinked `SKILL.md` was followed.

    Attributes:
        failed_at: The `SKILL.md` at its resolved directory, which the skill entry may be a link to.
        refusal: Why the operating system refused the lookup.
    """

    failed_at: RootRelativePath
    refusal: OsRefusal


@dataclass(frozen=True, slots=True)
class UninspectableSkillFile:
    """A symlinked `SKILL.md` leads to no file, and where its chain goes could not be inspected.

    Attributes:
        skill_file: The `SKILL.md` at its resolved directory, which the skill entry may be a link to.
        failed_at: The entry that could not be inspected, which may be one on the way.
        refusal: Why the operating system refused the inspection.
    """

    skill_file: RootRelativePath
    failed_at: RootRelativePath
    refusal: OsRefusal


# Every condition a unit of the declaration fails with.
type LoadFailureCondition = (
    StructureLoadFailure
    | UnlistableDirectory
    | UnlistableCorpusDirectory
    | UnresolvableSkillsDirectory
    | UninspectableSkillsDirectory
    | UnlistableSkillsDirectory
    | UnresolvableSkillEntry
    | UninspectableSkillEntry
    | UnlistableSkillDirectory
    | UnresolvableSkillFile
    | UninspectableSkillFile
)


@dataclass(frozen=True, slots=True)
class LoadFailure:
    """One unit of the declaration that failed to load: where, and why.

    Attributes:
        path: Root-relative path of the unit where the declaration reaches it: a structure file, a directory, a
            skills directory as an agent declares it, a skill entry or the `SKILL.md` of one. A condition that
            happens at the place a link leads to keeps that place in its `failed_at`.
        condition: What failed there.
    """

    path: RootRelativePath
    condition: LoadFailureCondition
