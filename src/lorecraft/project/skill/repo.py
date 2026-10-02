"""Discover skills directories, the skills in them and the resources of a skill, and read a skill or a resource.

Every path the repository takes or returns is root-relative: a skills directory is joined to the workspace root
only inside `FileSystem`. The repository finds which directories are skills and which files inside a skill are
its resources, and reads a `SKILL.md` or a resource as text; whether a skill's frontmatter has the shape the
Agent Skills specification defines is decided above it, and so is which skills directories to look in, which the
agents state.

A skill is `<skills directory>/<skill name>/SKILL.md` and nothing else, or a directory a command names with a
`SKILL.md` at its root. Symlinks are followed here, unlike under `docs/`: an agent's skills directory is commonly
a link to another one, a skill entry a link to where the skill's files live, and a `SKILL.md` a link to where its
text lives. A skill is still named where it is listed, under the resolved skills directory of an agent or under the
directory a command names as spelled: the place a link leads to is not a skill of its own. Where each link
leads is recorded beside the ref, in its location, so what a skill is named by and where its files live are both
known. A link whose chain leaves the repository is not followed out of it, and is recorded instead as an
`OutsideSymlink`, where an agent reaches it: the snapshot holds nothing outside the root to follow it into.

Nothing here logs: the command that loads the model catches every `Error` that escapes it and reports it,
so every handler below re-raises without logging.
"""

from collections import deque
from dataclasses import dataclass
from typing import assert_never

from lorecraft.agents import SKILL_ENTRY_FILENAME
from lorecraft.core.error import Error
from lorecraft.core.path import RootRelativePath
from lorecraft.project.layout import DOCUMENT_SUFFIX
from lorecraft.vfs import (
    DirListError,
    DirResolveError,
    EntryInspectError,
    EntryKind,
    FileReadError,
    FileResolveError,
    FileSystem,
    ResolvedPath,
    RootExit,
    TextDecodeError,
    UnrecordedFileError,
)

from .outside import OutsideSymlink
from .ref import SkillLocation, SkillRef, SkillResourceLocation, SkillResourceRef


@dataclass(frozen=True, slots=True)
class Skill:
    """A skill's ``SKILL.md`` at the moment it was read.

    Attributes:
        ref: The skill's identity in the workspace model.
        text: The whole ``SKILL.md`` decoded as UTF-8, frontmatter and body.
    """

    ref: SkillRef
    text: str


@dataclass(frozen=True, slots=True)
class SkillResource:
    """A skill's resource at the moment it was read.

    Attributes:
        ref: The resource's identity, named where an agent reaches it.
        text: The whole resource decoded as UTF-8.
    """

    ref: SkillResourceRef
    text: str


@dataclass(frozen=True, slots=True)
class SkillsListing:
    """What one resolved skills directory holds, as `Repository.list_skills` finds it.

    Attributes:
        skills: The location of every skill directly inside it, sorted by ref.
        outside_symlinks: Every entry, and every entry's `SKILL.md`, whose symlink chain leaves the repository,
            sorted by path. Such an entry is not a skill, and is in `skills` under no ref.
    """

    skills: tuple[SkillLocation, ...]
    outside_symlinks: tuple[OutsideSymlink, ...]


@dataclass(frozen=True, slots=True)
class SkillResourceListing:
    """What the walk over one skill's files finds, as `Repository.list_skill_resources` lists it.

    Attributes:
        resources: The location of every resource of the skill, sorted by ref.
        outside_symlinks: Every symlink the walk met whose chain leaves the repository, named where an agent
            reaches it under the skill's entry, sorted by path. The walk does not follow one.
    """

    resources: tuple[SkillResourceLocation, ...]
    outside_symlinks: tuple[OutsideSymlink, ...]


class SkillsDirListError(Error):
    """A skills directory exists but cannot be listed.

    Attributes:
        skills_dir: The skills directory whose skills were being listed.
        source: The failure to list it.
    """

    skills_dir: RootRelativePath
    source: DirListError

    def __init__(self, skills_dir: RootRelativePath, *, source: DirListError) -> None:
        self.skills_dir = skills_dir
        self.source = source
        super().__init__(f'cannot list the skills in {skills_dir}')
        self.__cause__ = source


class SkillEntryResolveError(Error):
    """A symlinked entry in a skills directory cannot be resolved because the operating system refused a lookup.

    Attributes:
        entry: The entry whose link was being followed.
        source: The failure to resolve it.
    """

    entry: RootRelativePath
    source: DirResolveError | EntryInspectError

    def __init__(self, entry: RootRelativePath, *, source: DirResolveError | EntryInspectError) -> None:
        self.entry = entry
        self.source = source
        super().__init__(f'cannot resolve skill entry {entry}')
        self.__cause__ = source


class SkillDirListError(Error):
    """A skill directory exists but cannot be listed to look for its ``SKILL.md``.

    Attributes:
        directory: The skill directory being looked in.
        source: The failure to list it.
    """

    directory: RootRelativePath
    source: DirListError

    def __init__(self, directory: RootRelativePath, *, source: DirListError) -> None:
        self.directory = directory
        self.source = source
        super().__init__(f'cannot look for {SKILL_ENTRY_FILENAME} in {directory}')
        self.__cause__ = source


class SkillFileResolveError(Error):
    """A symlinked ``SKILL.md`` cannot be resolved because the operating system refused a lookup.

    Attributes:
        skill_file: The ``SKILL.md`` whose link was being followed.
        source: The failure to resolve it.
    """

    skill_file: RootRelativePath
    source: FileResolveError | EntryInspectError

    def __init__(self, skill_file: RootRelativePath, *, source: FileResolveError | EntryInspectError) -> None:
        self.skill_file = skill_file
        self.source = source
        super().__init__(f'cannot resolve {skill_file}')
        self.__cause__ = source


class SkillReadError(Error):
    """A skill listed in the model cannot be read: its ``SKILL.md`` is missing or unreadable.

    Attributes:
        ref: The skill whose ``SKILL.md`` could not be read.
        source: The failure to read the file.
    """

    ref: SkillRef
    source: FileReadError | UnrecordedFileError

    def __init__(self, ref: SkillRef, *, source: FileReadError | UnrecordedFileError) -> None:
        self.ref = ref
        self.source = source
        super().__init__(f'cannot read skill {ref.path}')
        self.__cause__ = source


class SkillDecodeError(Error):
    """A skill's ``SKILL.md`` is not UTF-8; the check reports this as a finding.

    Attributes:
        ref: The skill whose ``SKILL.md`` could not be decoded.
        source: The failure to decode the file.
    """

    ref: SkillRef
    source: TextDecodeError

    def __init__(self, ref: SkillRef, *, source: TextDecodeError) -> None:
        self.ref = ref
        self.source = source
        super().__init__(f'skill {ref.path} is not UTF-8')
        self.__cause__ = source


class SkillResourcesListError(Error):
    """A directory the walk over a skill's resources entered cannot be listed.

    Attributes:
        skill: The skill whose resources were being listed.
        directory: The resolved directory that could not be listed.
        source: The failure to list it.
    """

    skill: SkillRef
    directory: RootRelativePath
    source: DirListError

    def __init__(self, skill: SkillRef, directory: RootRelativePath, *, source: DirListError) -> None:
        self.skill = skill
        self.directory = directory
        self.source = source
        super().__init__(f'cannot list {directory} for the resources of skill {skill.directory}')
        self.__cause__ = source


class SkillResourcesSymlinkResolveError(Error):
    """A symlink the walk over a skill's resources met cannot be resolved: the operating system refused a lookup.

    Attributes:
        skill: The skill whose resources were being listed.
        symlink: The symlink being followed, at its resolved path.
        source: The failure to resolve it, as a directory, as a file, or to where it leaves the repository.
    """

    skill: SkillRef
    symlink: RootRelativePath
    source: DirResolveError | FileResolveError | EntryInspectError

    def __init__(
        self,
        skill: SkillRef,
        symlink: RootRelativePath,
        *,
        source: DirResolveError | FileResolveError | EntryInspectError,
    ) -> None:
        self.skill = skill
        self.symlink = symlink
        self.source = source
        super().__init__(f'cannot resolve symlink {symlink} for the resources of skill {skill.directory}')
        self.__cause__ = source


class SkillResourceReadError(Error):
    """A skill's resource cannot be read: the file its location records is missing or unreadable.

    Attributes:
        ref: The resource that could not be read.
        source: The failure to read it.
    """

    ref: SkillResourceRef
    source: FileReadError | UnrecordedFileError

    def __init__(self, ref: SkillResourceRef, *, source: FileReadError | UnrecordedFileError) -> None:
        self.ref = ref
        self.source = source
        super().__init__(f'cannot read resource {ref.path} of skill {ref.skill.directory}')
        self.__cause__ = source


class SkillResourceDecodeError(Error):
    """A skill's resource is not UTF-8; a check reports this as a finding.

    Attributes:
        ref: The resource that could not be decoded.
        source: The failure to decode it.
    """

    ref: SkillResourceRef
    source: TextDecodeError

    def __init__(self, ref: SkillResourceRef, *, source: TextDecodeError) -> None:
        self.ref = ref
        self.source = source
        super().__init__(f'resource {ref.path} of skill {ref.skill.directory} is not UTF-8')
        self.__cause__ = source


class Repository:
    """Discover skills directories, the skills directly inside them and the resources of a skill; read them."""

    def __init__(self, fs: FileSystem) -> None:
        """Remember the seam; performs no I/O.

        Args:
            fs: View of the repository every listing, resolution and read goes through; a disk or a snapshot.
        """
        self._fs = fs

    def find_skills_dir(self, skills_dir: RootRelativePath) -> ResolvedPath | None:
        """The resolved directory a skills directory leads to, following every symlink on the way.

        Args:
            skills_dir: Skills directory as the layout names it, such as `.agents/skills`; it may be a link.

        Returns:
            The resolved directory, root-relative, or `None` when the repository has no such skills directory:
            the path is missing, a link dangles or loops, the target is not a directory, or it lies outside
            the root.

        Raises:
            DirResolveError: If the operating system refuses the lookup.
        """
        # A refused lookup is the resolve's own, with the skills directory as its path: nothing to add here.
        return self._fs.find_dir(skills_dir)

    def find_dir(self, path: RootRelativePath) -> ResolvedPath | None:
        """The resolved directory a path leads to, following every symlink on the way, such as one a command names.

        Args:
            path: A root-relative path, as spelled; it may be a link or lead through one.

        Returns:
            The resolved directory, root-relative, or `None` when the path leads to no directory under the root.

        Raises:
            DirResolveError: If the operating system refuses the lookup.
        """
        return self._fs.find_dir(path)

    def find_skills_dir_exit(self, skills_dir: RootRelativePath) -> OutsideSymlink | None:
        """The skills directory as a symlink leading outside the repository, or `None` when it does not lead out.

        Args:
            skills_dir: Skills directory as the layout names it; asked when `find_skills_dir` found no directory.

        Raises:
            EntryInspectError: If an entry on the way cannot be inspected, or a link's target cannot be read.
        """
        # A refused lookup is the view's own, with the path it stopped at: nothing to add here.
        leaves_at = self._fs.find_root_exit(skills_dir)
        if leaves_at is None:
            return None
        return OutsideSymlink(skills_dir, leaves_at)

    def list_skills(self, skills_dir: ResolvedPath) -> SkillsListing:
        """The location of every skill directly inside one skills directory, sorted by name, and its outside links.

        A skill is an entry that is, or leads to, a directory under the root holding a `SKILL.md` that is,
        or leads to, a regular file under the root. The ref names the entry, `<skills_dir>/<entry name>`,
        whether or not it is a symlink, so two entries leading to one directory are two skills, as an agent
        sees them; its location records the resolved directory and the resolved `SKILL.md` each leads to.

        An entry whose link leads outside the root, or an entry whose `SKILL.md` is a link leading outside it, is
        no skill: it is recorded as an `OutsideSymlink`, at the entry or at `<entry>/SKILL.md`. Left out
        silently: a file beside the skills, an entry whose link dangles or loops, and a directory with no
        `SKILL.md` or with one that is a directory or a link that dangles or loops. A missing skills directory
        lists as nothing.

        Args:
            skills_dir: A resolved skills directory, as `find_skills_dir` returns it: a link is not followed
                here.

        Raises:
            SkillsDirListError: If the skills directory cannot be listed.
            SkillEntryResolveError: If a symlinked entry cannot be resolved.
            SkillDirListError: If a skill directory cannot be listed.
            SkillFileResolveError: If a symlinked `SKILL.md` cannot be resolved.
        """
        return self._list_entries(skills_dir, skills_dir)

    def list_named_skills(self, directory: RootRelativePath, resolved_directory: ResolvedPath) -> SkillsListing:
        """The skills in a directory a command names: the directory itself, or each skill directly inside it.

        The directory is one skill when a `SKILL.md` is at its root: a regular file, or a link to one under the
        root. Otherwise it is read as a skills directory, as `list_skills` reads one, so each entry holding a
        `SKILL.md` is a skill. Either way a skill is named under `directory`, as the command spelled it, and
        located at the resolved paths it leads to; a symlink leading outside the root is recorded as `list_skills`
        records one, under `directory` too.

        A `SKILL.md` at the root whose link leaves the root still makes the directory one skill, so it lists no
        skill and records that link. A `SKILL.md` that is a directory, or a link that dangles or loops, is none.

        Args:
            directory: The directory as the command spelled it, root-relative; it may be a link or lead through one.
            resolved_directory: The resolved directory `directory` leads to, as `find_skills_dir` returns it.

        Raises:
            SkillsDirListError: If the directory is read as a skills directory and cannot be listed.
            SkillEntryResolveError: If a symlinked entry cannot be resolved.
            SkillDirListError: If the directory, or a skill directory in it, cannot be listed.
            SkillFileResolveError: If a symlinked `SKILL.md` cannot be resolved.
        """
        skill_file = self._find_skill_file(resolved_directory)
        match skill_file:
            case RootRelativePath():
                location = SkillLocation(
                    SkillRef(directory), resolves_to=resolved_directory, file_resolves_to=skill_file
                )
                return SkillsListing(skills=(location,), outside_symlinks=())
            case RootExit():
                outside = OutsideSymlink(directory / SKILL_ENTRY_FILENAME, skill_file)
                return SkillsListing(skills=(), outside_symlinks=(outside,))
            case None:
                return self._list_entries(directory, resolved_directory)
            case _:
                assert_never(skill_file)

    def _list_entries(self, skills_dir: RootRelativePath, resolved_skills_dir: ResolvedPath) -> SkillsListing:
        """The location of every skill directly inside a skills directory, and its outside links, each sorted.

        The rules are `list_skills`'s. Only the names differ: each skill and each outside link is named under
        `skills_dir`, while every entry is listed and resolved under `resolved_skills_dir`, where it really is.

        Args:
            skills_dir: The directory the skills are named under: the resolved one for an agent's skills directory,
                and the one a command spelled for a directory it names.
            resolved_skills_dir: The resolved directory `skills_dir` leads to, the one listed.

        Raises:
            SkillsDirListError: If the resolved skills directory cannot be listed.
            SkillEntryResolveError: If a symlinked entry cannot be resolved.
            SkillDirListError: If a skill directory cannot be listed.
            SkillFileResolveError: If a symlinked `SKILL.md` cannot be resolved.
        """
        try:
            entries = self._fs.list_dir(resolved_skills_dir)
        except DirListError as exc:
            raise SkillsDirListError(resolved_skills_dir, source=exc) from exc

        # The seam lists entries in name order, so the locations and the outside links come out sorted.
        locations: list[SkillLocation] = []
        outside_symlinks: list[OutsideSymlink] = []
        for entry in entries:
            directory = skills_dir / entry.name
            resolved_entry = resolved_skills_dir / entry.name
            if entry.kind is EntryKind.DIRECTORY:
                # The skills directory is resolved and so is this entry: nothing is left to resolve.
                files_directory = ResolvedPath(resolved_entry)
            elif entry.kind is EntryKind.SYMLINK:
                files_directory = self._find_entry_dir(resolved_entry)
                if files_directory is None:
                    leaves_at = self._find_entry_exit(resolved_entry)
                    if leaves_at is not None:
                        outside_symlinks.append(OutsideSymlink(directory, leaves_at))
            else:
                files_directory = None
            if files_directory is None:
                continue
            skill_file = self._find_skill_file(files_directory)
            match skill_file:
                case RootRelativePath():
                    locations.append(
                        SkillLocation(SkillRef(directory), resolves_to=files_directory, file_resolves_to=skill_file)
                    )
                case RootExit():
                    # Named under the entry, as the skill would have been, not under the resolved directory.
                    outside_symlinks.append(OutsideSymlink(directory / SKILL_ENTRY_FILENAME, skill_file))
                case None:
                    pass
                case _:
                    assert_never(skill_file)
        return SkillsListing(skills=tuple(locations), outside_symlinks=tuple(outside_symlinks))

    def get_skill(self, ref: SkillRef) -> Skill:
        """Read one skill's `SKILL.md`, through the link its entry may be.

        Args:
            ref: Skill to read, as `list_skills` names it; its path is read through the seam.

        Raises:
            SkillDecodeError: If the file is not UTF-8.
            SkillReadError: If the file is missing or unreadable.
        """
        try:
            text = self._fs.read_text(ref.path)
        except TextDecodeError as exc:
            raise SkillDecodeError(ref, source=exc) from exc
        except (FileReadError, UnrecordedFileError) as exc:
            raise SkillReadError(ref, source=exc) from exc
        return Skill(ref, text)

    def list_skill_resources(self, location: SkillLocation) -> SkillResourceListing:
        """The location of every resource of one skill, sorted by ref, and the symlinks in it leading outside.

        The walk starts at the skill's resolved directory and goes down every directory inside it, at any depth. A
        file is a resource when its name ends in `.md` and it is not the skill's own top-level `SKILL.md`; a
        `SKILL.md` below the top level is one like any other. Each resource is named where an agent reaches it,
        under `location.ref.directory`, and its location records the resolved file that path leads to.

        Symlinks inside the skill are followed. One that leads to a directory under the root is entered, and the
        files in it are named through the symlink; one whose name ends in `.md` and that leads to a regular file
        under the root is listed, with that file as its resolved one. A symlink whose chain leaves the root, whatever
        its name, is not followed and is recorded as an `OutsideSymlink`, named where an agent reaches it. Left out
        silently: a file whose name does not end in `.md`, and a symlink that dangles or loops.

        Three rules keep the walk finite and the resources the skill's own:

        - No resolved directory is entered twice, so two directories that link to each other end the walk.
        - A directory that holds the skill's own directory is never entered, whether the resolved directory the
          skill's files live in or the directory the skill is named by, its entry in the skills directory. That
          keeps out `references/up -> ../..` in a regular skill, and `agents -> ../../.agents/skills` in a skill
          whose entry links to `skills/audit`: each holds other skills' files, or this skill's again.
        - A symlink is followed only once no directory is left to enter, so every directory inside the skill is
          named where it really is, and a symlink back into the skill adds nothing.

        Reads no file's content, and nothing outside the root.

        Args:
            location: The skill whose resources are listed, as `list_skills` locates it; the walk starts at
                `location.resolves_to`.

        Raises:
            SkillResourcesListError: If a directory the walk enters cannot be listed.
            SkillResourcesSymlinkResolveError: If a symlink the walk meets cannot be resolved.
        """
        return _SkillResourcesWalk(self._fs, location).run()

    def get_skill_resource(self, location: SkillResourceLocation) -> SkillResource:
        """Read one resource of a skill, at the resolved file its location records.

        Args:
            location: The resource to read, as `list_skill_resources` locates it; `location.resolves_to` is read
                through the seam, never `location.ref.path`.

        Raises:
            SkillResourceDecodeError: If the resource is not UTF-8.
            SkillResourceReadError: If the resource's file is missing or unreadable.
        """
        try:
            text = self._fs.read_text(location.resolves_to)
        except TextDecodeError as exc:
            raise SkillResourceDecodeError(location.ref, source=exc) from exc
        except (FileReadError, UnrecordedFileError) as exc:
            raise SkillResourceReadError(location.ref, source=exc) from exc
        return SkillResource(location.ref, text)

    def _find_entry_dir(self, entry: RootRelativePath) -> ResolvedPath | None:
        """The resolved directory a symlinked entry leads to, or `None` when no directory under the root is there.

        Args:
            entry: Symlinked entry directly inside a skills directory.

        Raises:
            SkillEntryResolveError: If the operating system refuses the lookup.
        """
        try:
            return self._fs.find_dir(entry)
        except DirResolveError as exc:
            raise SkillEntryResolveError(entry, source=exc) from exc

    def _find_entry_exit(self, entry: RootRelativePath) -> RootExit | None:
        """Where a symlinked entry's chain leaves the root, or `None` when it does not.

        Args:
            entry: Symlinked entry directly inside a skills directory, one that leads to no directory under the
                root.

        Raises:
            SkillEntryResolveError: If the operating system refuses the lookup.
        """
        try:
            return self._fs.find_root_exit(entry)
        except EntryInspectError as exc:
            raise SkillEntryResolveError(entry, source=exc) from exc

    def _find_skill_file(self, directory: ResolvedPath) -> ResolvedPath | RootExit | None:
        """The resolved file of the `SKILL.md` in `directory`, where its link leaves the root, or `None`.

        A `SKILL.md` that is a regular file is its own resolved file. One that is a symlink counts when it leads
        to a regular file under the root, and that file is its resolved one; when its chain leaves the root, where it
        leaves is returned instead. A directory of that name, or a link that dangles or loops, counts for nothing.

        Args:
            directory: A resolved directory, so a `SKILL.md` listed in it sits at a resolved path.

        Raises:
            SkillDirListError: If the directory cannot be listed.
            SkillFileResolveError: If a linked `SKILL.md` cannot be resolved.
        """
        try:
            entries = self._fs.list_dir(directory)
        except DirListError as exc:
            raise SkillDirListError(directory, source=exc) from exc

        skill_file = directory / SKILL_ENTRY_FILENAME
        for entry in entries:
            if entry.name != SKILL_ENTRY_FILENAME:
                continue
            if entry.kind is EntryKind.FILE:
                # A regular file listed in a resolved directory: no symlink is on the way to it or at it.
                return ResolvedPath(skill_file)
            if entry.kind is EntryKind.SYMLINK:
                try:
                    resolved_file = self._fs.find_file(skill_file)
                    if resolved_file is not None:
                        return resolved_file
                    return self._fs.find_root_exit(skill_file)
                except (FileResolveError, EntryInspectError) as exc:
                    raise SkillFileResolveError(skill_file, source=exc) from exc
        return None


@dataclass(frozen=True, slots=True)
class _PendingDirectory:
    """A directory the walk over a skill's resources has yet to enter.

    Attributes:
        named: Where an agent reaches the directory, under the skill's ref directory.
        resolved: The resolved directory it is, the one listed.
    """

    named: RootRelativePath
    resolved: ResolvedPath


class _SkillResourcesWalk:
    """One walk over the resources of a skill, the steps `Repository.list_skill_resources` carries out.

    Every directory is held as a `_PendingDirectory`: the path an agent reaches it at, under the skill's ref
    directory, and the resolved directory it is, which is the one listed. A file's name is joined to the first,
    and its resolved path to the second. Directories and symlinks wait in two queues, and a symlink is followed
    only once no directory is left to enter.
    """

    def __init__(self, fs: FileSystem, location: SkillLocation) -> None:
        """Start a walk at the skill's resolved directory; performs no I/O.

        Args:
            fs: View every listing and resolution goes through.
            location: The skill whose resources are walked.
        """
        self._fs = fs
        self._location = location
        self._entered: set[ResolvedPath] = set()
        self._resources: list[SkillResourceLocation] = []
        self._outside_symlinks: list[OutsideSymlink] = []
        # Each queue holds its entries in the order the walk met them. A symlink waits as (path an agent reaches
        # it at, its own path in a resolved directory); that second path is not resolved, since it is a link.
        self._directories: deque[_PendingDirectory] = deque()
        self._symlinks: deque[tuple[RootRelativePath, RootRelativePath]] = deque()
        self._directories.append(_PendingDirectory(location.ref.directory, location.resolves_to))

    def run(self) -> SkillResourceListing:
        """Walk the skill to the end, and return every resource and outside symlink found, each sorted; call once.

        Raises:
            SkillResourcesListError: If a directory the walk enters cannot be listed.
            SkillResourcesSymlinkResolveError: If a symlink the walk meets cannot be resolved.
        """
        while self._directories or self._symlinks:
            # Symlinks wait until no directory is left: every resolved directory inside the skill is then entered first
            # and named by its resolved path, so a symlink leading to one afterwards adds nothing.
            if self._directories:
                pending = self._directories.popleft()
                self._enter(pending.named, pending.resolved)
            else:
                named, symlink = self._symlinks.popleft()
                self._follow(named, symlink)
        outside_symlinks = sorted(self._outside_symlinks, key=lambda outside: outside.path)
        return SkillResourceListing(resources=tuple(sorted(self._resources)), outside_symlinks=tuple(outside_symlinks))

    def _enter(self, named: RootRelativePath, resolved: ResolvedPath) -> None:
        """List one resolved directory, unless it was entered already or holds the skill's own directory.

        Its resources are kept, its directories queued to be entered, and its symlinks queued to be followed.

        Args:
            named: Where an agent reaches the directory, under the skill's ref directory.
            resolved: The resolved directory, the one listed.

        Raises:
            SkillResourcesListError: If the directory cannot be listed.
        """
        # Keeps out a directory entered already, which ends symlink loops, and one holding the skill's own
        # directory, resolved or as named in its skills directory, which would count other skills' files as its own.
        if (
            resolved in self._entered
            or resolved in self._location.resolves_to.parents
            or resolved in self._location.ref.directory.parents
        ):
            return
        self._entered.add(resolved)
        try:
            entries = self._fs.list_dir(resolved)
        except DirListError as exc:
            raise SkillResourcesListError(self._location.ref, resolved, source=exc) from exc

        for entry in entries:
            entry_named = named / entry.name
            entry_resolved = resolved / entry.name
            # A directory or a file listed in a resolved directory is resolved too: no symlink is on the way to it
            # or at it. A symlink is not, so it waits under its own path to be followed.
            if entry.kind is EntryKind.DIRECTORY:
                self._directories.append(_PendingDirectory(entry_named, ResolvedPath(entry_resolved)))
            elif entry.kind is EntryKind.SYMLINK:
                self._symlinks.append((entry_named, entry_resolved))
            elif entry.kind is EntryKind.FILE and self._is_resource_name(entry_named):
                resource = SkillResourceRef(self._location.ref, entry_named)
                self._resources.append(SkillResourceLocation(resource, ResolvedPath(entry_resolved)))

    def _follow(self, named: RootRelativePath, symlink: RootRelativePath) -> None:
        """Queue the directory a symlink leads to, keep the resource it leads to, or record it leading outside.

        Args:
            named: Where an agent reaches the symlink, under the skill's ref directory.
            symlink: The symlink at its resolved path, in a resolved directory, so it is the one symlink on the way.

        Raises:
            SkillResourcesSymlinkResolveError: If the operating system refuses the lookup.
        """
        try:
            directory = self._fs.find_dir(symlink)
        except DirResolveError as exc:
            raise SkillResourcesSymlinkResolveError(self._location.ref, symlink, source=exc) from exc
        if directory is not None:
            self._directories.append(_PendingDirectory(named, directory))
            return

        # Asked of every symlink, whatever its name: one leading outside the root is reported, not just skipped.
        try:
            leaves_at = self._fs.find_root_exit(symlink)
        except EntryInspectError as exc:
            raise SkillResourcesSymlinkResolveError(self._location.ref, symlink, source=exc) from exc
        if leaves_at is not None:
            self._outside_symlinks.append(OutsideSymlink(named, leaves_at))
            return

        # The name is checked before the lookup, so a symlink not named `.md` is never resolved as a file.
        if not self._is_resource_name(named):
            return
        try:
            file = self._fs.find_file(symlink)
        except FileResolveError as exc:
            raise SkillResourcesSymlinkResolveError(self._location.ref, symlink, source=exc) from exc
        if file is not None:
            self._resources.append(SkillResourceLocation(SkillResourceRef(self._location.ref, named), file))

    def _is_resource_name(self, named: RootRelativePath) -> bool:
        """Whether a file an agent reaches at `named` is one of the skill's resources.

        Args:
            named: Where an agent reaches the file; the skill's own top-level `SKILL.md` is not one of them.
        """
        return named.name.endswith(DOCUMENT_SUFFIX) and named != self._location.ref.path
