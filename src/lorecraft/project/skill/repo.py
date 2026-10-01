"""Discover skills directories, the skills in them and the resources of a skill, and read a skill or a resource.

Every path the repository takes or returns is root-relative: a skills directory is joined to the workspace root
only inside `FileSystem`. The repository finds which directories are skills and which files inside a skill are
its resources, and reads a `SKILL.md` or a resource as text; whether a skill's frontmatter has the shape the
Agent Skills specification defines is decided above it, and so is which skills directories to look in, which the
agents state.

A skill is `<skills directory>/<skill name>/SKILL.md` and nothing else. Symlinks are followed here, unlike
under `docs/`: an agent's skills directory is commonly a link to another one, a skill entry a link to where
the skill's files live, and a `SKILL.md` a link to where its text lives. A skill is still named where it is
listed, under the real skills directory: the place a link leads to is not a skill of its own. Where each link
leads is recorded beside the ref, in its location, so what a skill is named by and where its files live are both
known.

Nothing here logs: the command that loads the model catches every `Error` that escapes it and reports it,
so every handler below re-raises without logging.
"""

from collections import deque
from dataclasses import dataclass

from lorecraft.agents import SKILL_ENTRY_FILENAME
from lorecraft.core.error import Error
from lorecraft.core.path import RootRelativePath
from lorecraft.project.layout import DOCUMENT_SUFFIX
from lorecraft.vfs import (
    DirListError,
    DirResolveError,
    EntryKind,
    FileReadError,
    FileResolveError,
    FileSystem,
    TextDecodeError,
    UnrecordedFileError,
)

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
    source: DirResolveError

    def __init__(self, entry: RootRelativePath, *, source: DirResolveError) -> None:
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
    source: FileResolveError

    def __init__(self, skill_file: RootRelativePath, *, source: FileResolveError) -> None:
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
        directory: The real directory that could not be listed.
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
        symlink: The symlink being followed, at its real path.
        source: The failure to resolve it, as a directory or else as a file.
    """

    skill: SkillRef
    symlink: RootRelativePath
    source: DirResolveError | FileResolveError

    def __init__(
        self, skill: SkillRef, symlink: RootRelativePath, *, source: DirResolveError | FileResolveError
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

    def find_skills_dir(self, skills_dir: RootRelativePath) -> RootRelativePath | None:
        """The real directory a skills directory leads to, following every symlink on the way.

        Args:
            skills_dir: Skills directory as the layout names it, such as `.agents/skills`; it may be a link.

        Returns:
            The real directory, root-relative, or `None` when the repository has no such skills directory:
            the path is missing, a link dangles or loops, the target is not a directory, or it lies outside
            the root.

        Raises:
            DirResolveError: If the operating system refuses the lookup.
        """
        # A refused lookup is the resolve's own, with the skills directory as its path: nothing to add here.
        return self._fs.find_real_dir(skills_dir)

    def list_skills(self, skills_dir: RootRelativePath) -> tuple[SkillLocation, ...]:
        """The location of every skill directly inside one skills directory, sorted by name.

        A skill is an entry that is, or leads to, a directory under the root holding a ``SKILL.md`` that is,
        or leads to, a regular file under the root. The ref names the entry, ``<skills_dir>/<entry name>``,
        whether or not it is a symlink, so two entries leading to one directory are two skills, as an agent
        sees them; its location records the real directory and the real ``SKILL.md`` each leads to.

        Left out silently: a file beside the skills, an entry whose link dangles, loops or leads outside the
        root, and a directory with no ``SKILL.md`` or with one that is a directory or a link leading to no
        file under the root. A missing skills directory lists as nothing.

        Args:
            skills_dir: A real skills directory, as ``find_skills_dir`` returns it: a link is not followed
                here.

        Raises:
            SkillsDirListError: If the skills directory cannot be listed.
            SkillEntryResolveError: If a symlinked entry cannot be resolved.
            SkillDirListError: If a skill directory cannot be listed.
            SkillFileResolveError: If a symlinked ``SKILL.md`` cannot be resolved.
        """
        try:
            entries = self._fs.list_dir(skills_dir)
        except DirListError as exc:
            raise SkillsDirListError(skills_dir, source=exc) from exc

        # The seam lists entries in name order, so the locations come out sorted.
        locations: list[SkillLocation] = []
        for entry in entries:
            directory = skills_dir / entry.name
            if entry.kind is EntryKind.DIRECTORY:
                # The skills directory is real and so is this entry: nothing is left to resolve.
                files_directory = directory
            elif entry.kind is EntryKind.SYMLINK:
                files_directory = self._find_real_entry(directory)
            else:
                files_directory = None
            if files_directory is None:
                continue
            skill_file = self._find_skill_file(files_directory)
            if skill_file is not None:
                locations.append(
                    SkillLocation(SkillRef(directory), resolves_to=files_directory, file_resolves_to=skill_file)
                )
        return tuple(locations)

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

    def list_skill_resources(self, location: SkillLocation) -> tuple[SkillResourceLocation, ...]:
        """The location of every resource of one skill, sorted by ref.

        The walk starts at the skill's real directory and goes down every directory inside it, at any depth. A
        file is a resource when its name ends in `.md` and it is not the skill's own top-level `SKILL.md`; a
        `SKILL.md` below the top level is one like any other. Each resource is named where an agent reaches it,
        under `location.ref.directory`, and its location records the real file that path leads to.

        Symlinks inside the skill are followed. One that leads to a directory under the root is entered, and the
        files in it are named through the symlink; one whose name ends in `.md` and that leads to a regular file
        under the root is listed, with that file as its real one. Left out silently: a file whose name does not
        end in `.md`, and a symlink that dangles, loops or leads outside the root.

        Three rules keep the walk finite and the resources the skill's own:

        - No real directory is entered twice, so two directories that link to each other end the walk.
        - A directory that holds the skill's own directory is never entered, whether the real directory the
          skill's files live in or the directory the skill is named by, its entry in the skills directory. That
          keeps out `references/up -> ../..` in a regular skill, and `agents -> ../../.agents/skills` in a skill
          whose entry links to `skills/audit`: each holds other skills' files, or this skill's again.
        - A symlink is followed only once no directory is left to enter, so every directory inside the skill is
          named where it really is, and a symlink back into the skill adds nothing.

        Reads no file's content.

        Args:
            location: The skill whose resources are listed, as `list_skills` locates it; the walk starts at
                `location.resolves_to`.

        Raises:
            SkillResourcesListError: If a directory the walk enters cannot be listed.
            SkillResourcesSymlinkResolveError: If a symlink the walk meets cannot be resolved.
        """
        return _SkillResourcesWalk(self._fs, location).run()

    def get_skill_resource(self, location: SkillResourceLocation) -> SkillResource:
        """Read one resource of a skill, at the real file its location records.

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

    def _find_real_entry(self, entry: RootRelativePath) -> RootRelativePath | None:
        """The real directory a symlinked entry leads to, or `None` when no directory under the root is there.

        Args:
            entry: Symlinked entry directly inside a skills directory.

        Raises:
            SkillEntryResolveError: If the operating system refuses the lookup.
        """
        try:
            return self._fs.find_real_dir(entry)
        except DirResolveError as exc:
            raise SkillEntryResolveError(entry, source=exc) from exc

    def _find_skill_file(self, directory: RootRelativePath) -> RootRelativePath | None:
        """The real file of the ``SKILL.md`` in ``directory``, or ``None`` when it holds none.

        A ``SKILL.md`` that is a regular file is its own real file. One that is a symlink counts when it leads
        to a regular file under the root, and that file is its real one; a directory of that name counts for
        nothing.

        Args:
            directory: A real directory, so a ``SKILL.md`` listed in it sits at a real path.

        Raises:
            SkillDirListError: If the directory cannot be listed.
            SkillFileResolveError: If a linked ``SKILL.md`` cannot be resolved.
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
                return skill_file
            if entry.kind is EntryKind.SYMLINK:
                try:
                    return self._fs.find_real_file(skill_file)
                except FileResolveError as exc:
                    raise SkillFileResolveError(skill_file, source=exc) from exc
        return None


class _SkillResourcesWalk:
    """One walk over the resources of a skill, the steps `Repository.list_skill_resources` carries out.

    Every directory is held as a pair: the path an agent reaches it at, under the skill's ref directory, and the
    real directory it is, which is the one listed. A file's name is joined to the first, and its real path to the
    second. Directories and symlinks wait in two queues, and a symlink is followed only once no directory is left to
    enter.
    """

    def __init__(self, fs: FileSystem, location: SkillLocation) -> None:
        """Start a walk at the skill's real directory; performs no I/O.

        Args:
            fs: View every listing and resolution goes through.
            location: The skill whose resources are walked.
        """
        self._fs = fs
        self._location = location
        self._entered: set[RootRelativePath] = set()
        self._resources: list[SkillResourceLocation] = []
        # Each queue holds (path an agent reaches it at, real path), in the order the walk met them.
        self._directories: deque[tuple[RootRelativePath, RootRelativePath]] = deque()
        self._symlinks: deque[tuple[RootRelativePath, RootRelativePath]] = deque()
        self._directories.append((location.ref.directory, location.resolves_to))

    def run(self) -> tuple[SkillResourceLocation, ...]:
        """Walk the skill to the end, and return every resource found, sorted by ref; call once.

        Raises:
            SkillResourcesListError: If a directory the walk enters cannot be listed.
            SkillResourcesSymlinkResolveError: If a symlink the walk meets cannot be resolved.
        """
        while self._directories or self._symlinks:
            # Symlinks wait until no directory is left: every real directory inside the skill is then entered first
            # and named by its real path, so a symlink leading to one afterwards adds nothing.
            if self._directories:
                named, real = self._directories.popleft()
                self._enter(named, real)
            else:
                named, symlink = self._symlinks.popleft()
                self._follow(named, symlink)
        return tuple(sorted(self._resources))

    def _enter(self, named: RootRelativePath, real: RootRelativePath) -> None:
        """List one real directory, unless it was entered already or holds the skill's own directory.

        Its resources are kept, its directories queued to be entered, and its symlinks queued to be followed.

        Args:
            named: Where an agent reaches the directory, under the skill's ref directory.
            real: The real directory, the one listed.

        Raises:
            SkillResourcesListError: If the directory cannot be listed.
        """
        # Keeps out a directory entered already, which ends symlink loops, and one holding the skill's own
        # directory, real or as named in its skills directory, which would count other skills' files as its own.
        if (
            real in self._entered
            or real in self._location.resolves_to.parents
            or real in self._location.ref.directory.parents
        ):
            return
        self._entered.add(real)
        try:
            entries = self._fs.list_dir(real)
        except DirListError as exc:
            raise SkillResourcesListError(self._location.ref, real, source=exc) from exc

        for entry in entries:
            entry_named = named / entry.name
            entry_real = real / entry.name
            if entry.kind is EntryKind.DIRECTORY:
                self._directories.append((entry_named, entry_real))
            elif entry.kind is EntryKind.SYMLINK:
                self._symlinks.append((entry_named, entry_real))
            elif entry.kind is EntryKind.FILE and self._is_resource_name(entry_named):
                self._resources.append(
                    SkillResourceLocation(SkillResourceRef(self._location.ref, entry_named), entry_real)
                )

    def _follow(self, named: RootRelativePath, symlink: RootRelativePath) -> None:
        """Queue the directory a symlink leads to, or keep the resource it leads to; else leave it out.

        Args:
            named: Where an agent reaches the symlink, under the skill's ref directory.
            symlink: The symlink at its real path, in a real directory, so it is the one symlink on the way.

        Raises:
            SkillResourcesSymlinkResolveError: If the operating system refuses the lookup.
        """
        try:
            directory = self._fs.find_real_dir(symlink)
        except DirResolveError as exc:
            raise SkillResourcesSymlinkResolveError(self._location.ref, symlink, source=exc) from exc
        if directory is not None:
            self._directories.append((named, directory))
            return

        # The name is checked before the lookup, so a symlink not named `.md` is never resolved as a file.
        if not self._is_resource_name(named):
            return
        try:
            file = self._fs.find_real_file(symlink)
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
