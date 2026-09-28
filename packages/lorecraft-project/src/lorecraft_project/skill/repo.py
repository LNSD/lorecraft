"""Discover skill directories through the filesystem boundary.

Every path in and out is root-relative. The repository lists, resolves and probes; whether an entry is a
valid skill is decided above it. Content reads (``get_skill_md``, ``list_files``, ``read_file``) join this
class with the check migration.

Nothing here logs: the command that loads the model catches every ``Error`` that escapes it and reports it,
so every handler below re-raises without logging.
"""

from dataclasses import dataclass

from lorecraft_core.error import Error
from lorecraft_project.layout import SKILL_FILENAME
from lorecraft_vfs import EntryKind, FileSystem, ListDirError, ResolveDirError, RootRelativePath


@dataclass(frozen=True, slots=True)
class SkillEntry:
    """A DIRECTORY or SYMLINK entry directly inside a skills directory, before name validation.

    Attributes:
        path: Root-relative path as listed, unresolved.
        name: The entry name; may fail ``SkillName.parse`` (the loader leaves it out).
        kind: DIRECTORY or SYMLINK; files and other kinds are never listed.
    """

    path: RootRelativePath
    name: str
    kind: EntryKind


class ListSkillEntriesError(Error):
    """A skills directory exists but cannot be listed.

    Attributes:
        path: The root-relative skills directory that could not be listed.
    """

    path: RootRelativePath

    def __init__(self, path: RootRelativePath, detail: str) -> None:
        self.path = path
        super().__init__(f'cannot list skill entries in {path}: {detail}')


class ResolveSkillDirectoryError(Error):
    """A skills path cannot be resolved because the operating system refused a lookup.

    Attributes:
        path: The root-relative path whose symlink chain could not be followed.
    """

    path: RootRelativePath

    def __init__(self, path: RootRelativePath, detail: str) -> None:
        self.path = path
        super().__init__(f'cannot resolve skill directory {path}: {detail}')


class ProbeSkillMdError(Error):
    """A skill directory exists but cannot be listed for its SKILL.md.

    Attributes:
        path: The root-relative skill directory that could not be listed.
    """

    path: RootRelativePath

    def __init__(self, path: RootRelativePath, detail: str) -> None:
        self.path = path
        super().__init__(f'cannot look for {SKILL_FILENAME} in {path}: {detail}')


class Repository:
    """Discover skill directories under the canonical and agent skills directories."""

    def __init__(self, fs: FileSystem) -> None:
        """Remember the seam; performs no I/O."""
        self._fs = fs

    def list_entries(self, directory: RootRelativePath) -> tuple[SkillEntry, ...]:
        """DIRECTORY and SYMLINK entries directly inside ``directory``, sorted by name.

        Files and other kinds are dropped silently: a README beside the skills is not a skill. A missing
        directory lists as ``()``.

        Raises:
            ListSkillEntriesError: If the directory exists but cannot be listed.
        """
        try:
            entries = self._fs.list_dir(directory)
        except ListDirError as exc:
            raise ListSkillEntriesError(directory, exc.detail) from exc

        skill_entries: list[SkillEntry] = []
        for entry in entries:
            if entry.kind is EntryKind.DIRECTORY or entry.kind is EntryKind.SYMLINK:
                skill_entries.append(SkillEntry(directory / entry.name, entry.name, entry.kind))
        return tuple(skill_entries)

    def resolve_directory(self, path: RootRelativePath) -> RootRelativePath | None:
        """The real root-relative directory ``path`` leads to, following every symlink on the way.

        Returns:
            The real directory, or ``None`` when no directory under the root sits at the end of the
            chain: the path is missing, a link dangles or loops, the target is not a directory, or it lies
            outside the root.

        Raises:
            ResolveSkillDirectoryError: If the operating system refuses the lookup.
        """
        try:
            return self._fs.resolve_dir(path)
        except ResolveDirError as exc:
            raise ResolveSkillDirectoryError(path, exc.detail) from exc

    def has_skill_md(self, directory: RootRelativePath) -> bool:
        """True when ``directory`` holds a regular file named SKILL.md.

        Mirrors vercel's ``hasSkillMd().isFile()`` in skills.ts: a symlink or a directory of that name does
        not count. A missing directory holds no SKILL.md.

        Raises:
            ProbeSkillMdError: If the directory exists but cannot be listed.
        """
        try:
            entries = self._fs.list_dir(directory)
        except ListDirError as exc:
            raise ProbeSkillMdError(directory, exc.detail) from exc

        for entry in entries:
            if entry.name == SKILL_FILENAME and entry.kind is EntryKind.FILE:
                return True
        return False
