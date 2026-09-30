"""Discover skills directories and the skills in them, and read a skill, through the filesystem boundary.

Every path the repository takes or returns is root-relative: a skills directory is joined to the workspace root
only inside ``FileSystem``. The repository finds which directories are skills and reads a ``SKILL.md`` as text;
whether a skill's frontmatter has the shape the Agent Skills specification defines is decided above it, and so
is which skills directories to look in, which the agents state.

A skill is ``<skills directory>/<skill name>/SKILL.md`` and nothing else. Symlinks are followed here, unlike
under ``docs/``: an agent's skills directory is commonly a link to another one, a skill entry a link to where
the skill's files live, and a ``SKILL.md`` a link to where its text lives. A skill is still named where it is
listed, under the real skills directory: the place a link leads to is not a skill of its own. Where each link
leads is recorded beside the ref, in its location, so what a skill is named by and where its files live are both
known.

Nothing here logs: the command that loads the model catches every ``Error`` that escapes it and reports it,
so every handler below re-raises without logging.
"""

from dataclasses import dataclass

from lorecraft.agents import SKILL_ENTRY_FILENAME
from lorecraft.core.error import Error
from lorecraft.vfs import (
    DecodeTextError,
    EntryKind,
    FileSystem,
    ListDirError,
    ReadTextError,
    ResolveDirError,
    ResolveFileError,
    RootRelativePath,
)

from .ref import SkillLocation, SkillRef


@dataclass(frozen=True, slots=True)
class Skill:
    """A skill's ``SKILL.md`` at the moment it was read.

    Attributes:
        ref: The skill's identity in the workspace model.
        text: The whole ``SKILL.md`` decoded as UTF-8, frontmatter and body.
    """

    ref: SkillRef
    text: str


class ResolveSkillsDirError(Error):
    """A skills directory cannot be resolved because the operating system refused a lookup."""


class ListSkillsError(Error):
    """A skills directory, or a skill directory in it, exists but cannot be listed or resolved."""


class GetSkillError(Error):
    """A skill listed in the model cannot be read.

    Attributes:
        ref: The skill whose ``SKILL.md`` could not be read.
    """

    ref: SkillRef

    def __init__(self, ref: SkillRef, detail: str) -> None:
        self.ref = ref
        super().__init__(f'cannot read skill {ref.path}: {detail}')


class SkillDecodeError(GetSkillError):
    """The skill's ``SKILL.md`` is not UTF-8; the check reports this as a finding."""


class Repository:
    """Discover skills directories and the skills directly inside them, and read a skill."""

    def __init__(self, fs: FileSystem) -> None:
        """Remember the seam; performs no I/O."""
        self._fs = fs

    def resolve_skills_dir(self, skills_dir: RootRelativePath) -> RootRelativePath | None:
        """The real directory a skills directory leads to, following every symlink on the way.

        Returns:
            The real directory, root-relative, or ``None`` when the repository has no such skills directory:
            the path is missing, a link dangles or loops, the target is not a directory, or it lies outside
            the root.

        Raises:
            ResolveSkillsDirError: If the operating system refuses the lookup.
        """
        try:
            return self._fs.resolve_dir(skills_dir)
        except ResolveDirError as exc:
            raise ResolveSkillsDirError(f'cannot resolve skills directory {skills_dir}: {exc.detail}') from exc

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
            skills_dir: A real skills directory, as ``resolve_skills_dir`` returns it: a link is not followed
                here.

        Raises:
            ListSkillsError: If the skills directory or a skill directory cannot be listed, or an entry cannot
                be resolved.
        """
        try:
            entries = self._fs.list_dir(skills_dir)
        except ListDirError as exc:
            raise ListSkillsError(f'cannot list skills in {skills_dir}: {exc.detail}') from exc

        # The seam lists entries in name order, so the locations come out sorted.
        locations: list[SkillLocation] = []
        for entry in entries:
            directory = skills_dir / entry.name
            if entry.kind is EntryKind.DIRECTORY:
                # The skills directory is real and so is this entry: nothing is left to resolve.
                files_directory = directory
            elif entry.kind is EntryKind.SYMLINK:
                files_directory = self._resolve_entry(directory)
            else:
                files_directory = None
            if files_directory is None:
                continue
            skill_file = self._skill_file(files_directory)
            if skill_file is not None:
                locations.append(
                    SkillLocation(SkillRef(directory), resolves_to=files_directory, file_resolves_to=skill_file)
                )
        return tuple(locations)

    def get_skill(self, ref: SkillRef) -> Skill:
        """Read one skill's ``SKILL.md``, through the link its entry may be.

        Raises:
            SkillDecodeError: If the file is not UTF-8.
            GetSkillError: If the file is missing or unreadable.
        """
        # DecodeTextError is a ReadTextError, so the narrower clause must come first.
        try:
            text = self._fs.read_text(ref.path)
        except DecodeTextError as exc:
            raise SkillDecodeError(ref, exc.detail) from exc
        except ReadTextError as exc:
            raise GetSkillError(ref, exc.detail) from exc
        return Skill(ref, text)

    def _resolve_entry(self, entry: RootRelativePath) -> RootRelativePath | None:
        """The real directory a symlinked entry leads to, or ``None`` when no directory under the root is there.

        Raises:
            ListSkillsError: If the operating system refuses the lookup.
        """
        try:
            return self._fs.resolve_dir(entry)
        except ResolveDirError as exc:
            raise ListSkillsError(f'cannot resolve skill entry {entry}: {exc.detail}') from exc

    def _skill_file(self, directory: RootRelativePath) -> RootRelativePath | None:
        """The real file of the ``SKILL.md`` in ``directory``, or ``None`` when it holds none.

        A ``SKILL.md`` that is a regular file is its own real file. One that is a symlink counts when it leads
        to a regular file under the root, and that file is its real one; a directory of that name counts for
        nothing.

        Args:
            directory: A real directory, so a ``SKILL.md`` listed in it sits at a real path.

        Raises:
            ListSkillsError: If the directory cannot be listed, or a linked ``SKILL.md`` cannot be resolved.
        """
        try:
            entries = self._fs.list_dir(directory)
        except ListDirError as exc:
            raise ListSkillsError(f'cannot look for {SKILL_ENTRY_FILENAME} in {directory}: {exc.detail}') from exc

        skill_file = directory / SKILL_ENTRY_FILENAME
        for entry in entries:
            if entry.name != SKILL_ENTRY_FILENAME:
                continue
            if entry.kind is EntryKind.FILE:
                return skill_file
            if entry.kind is EntryKind.SYMLINK:
                try:
                    return self._fs.resolve_file(skill_file)
                except ResolveFileError as exc:
                    raise ListSkillsError(f'cannot resolve {skill_file}: {exc.detail}') from exc
        return None
