"""The identity of a skill and of each of its resources, separate from content and from where their files live.

The model lists which skills exist; the text of a `SKILL.md` is not part of it. A `SkillRef` is a skill's
key in the model, and its `path` is the root-relative location every finding reports. A `SkillLocation`
records where the skill's directory and its `SKILL.md` lead, as the snapshot saw them, so nothing above the
model has to follow a link again to learn it.

A resource, here, is a Markdown file inside a skill other than its own top-level `SKILL.md`, at any depth: the
files the Agent Skills specification places beside `SKILL.md`, as far as they are Markdown. A resource is named
the same way as its skill: a `SkillResourceRef` names it where an agent reaches it, by a `SkillRelativePath`
spelled from the skill's directory, so no ref can name a file outside its skill, and a `SkillResourceLocation`
records the resolved file that path leads to. The record refuses a path that is no resource, so no ref names the
skill's own `SKILL.md`, its directory or a file that is not Markdown. `SkillRef.find_resource` is where a ref is
built from a listing: it decides from the name alone which files are resources.

Each pair keeps a path as an agent names it, its identity, apart from the resolved path it leads to: a link
retargeted to another directory leaves the skill the same skill, named by the same ref, and changes only its
location.
"""

from dataclasses import dataclass
from functools import total_ordering
from typing import Final, Self

from lorecraft.agents import SKILL_ENTRY, SKILL_ENTRY_FILENAME
from lorecraft.core.error import Error
from lorecraft.core.path import PathComponent, RootRelativePath
from lorecraft.project.layout import DOCUMENT_SUFFIX
from lorecraft.vfs import ResolvedPath


# order=True so a collection of paths sorts by path, as the root-relative paths they wrap do.
@dataclass(frozen=True, slots=True, order=True)
class SkillRelativePath:
    """A path inside a skill, spelled from the skill's directory with POSIX separators, such as `references/a.md`.

    A valid path is a valid `RootRelativePath` with the skill's directory as its root: it is not absolute and holds
    no `..` component, so no spelling of it climbs out of the skill. `.` is the skill's directory itself. Parsing
    normalizes as `RootRelativePath` does. Which skill the path is inside is not part of it: a `SkillResourceRef`
    pairs the two.

    Attributes:
        value: The validated path, with the skill's directory as its root.
    """

    value: RootRelativePath

    @classmethod
    def parse(cls, raw: str) -> Self:
        """Return a validated path inside a skill.

        Args:
            raw: Path as spelled from the skill's directory, with POSIX separators; empty means the directory itself.

        Raises:
            RootRelativePathError: If the path is absolute or holds a `..` component.
        """
        return cls(RootRelativePath.parse(raw))

    def __str__(self) -> str:
        """The path with POSIX separators, spelled from the skill's directory, such as `references/a.md`."""
        return str(self.value)

    def __truediv__(self, other: PathComponent | RootRelativePath) -> SkillRelativePath:
        """This path joined with `other`, so the result stays inside the skill.

        Args:
            other: A `PathComponent` names one child of this path; a `RootRelativePath` names a descendant below it.
        """
        return SkillRelativePath(self.value / other)

    @property
    def name(self) -> PathComponent | None:
        """The last component, or `None` for the skill's directory."""
        return self.value.name

    def under(self, directory: RootRelativePath) -> RootRelativePath:
        """This path spelled from the root, through the skill directory it is spelled from.

        The one place a path inside a skill becomes root-relative. Neither side is absolute or holds a `..`, so
        neither does the join.

        Args:
            directory: The skill's directory, root-relative, such as `.agents/skills/review`.
        """
        return RootRelativePath(directory.value / self.value.value)


_SKILL_ENTRY_PATH: Final[SkillRelativePath] = SkillRelativePath.parse(SKILL_ENTRY_FILENAME)
"""The skill's own top-level `SKILL.md`, spelled from the skill's directory."""


def _is_resource_path(path: SkillRelativePath) -> bool:
    """Whether a file at `path` in a skill is a resource, decided from the name alone.

    A file is a resource when its name ends in the document suffix, `.md`, unless it is the skill's own top-level
    `SKILL.md`. A `SKILL.md` deeper in the skill, such as `examples/SKILL.md`, is a resource. `.`, the skill's
    directory, has no name, so it is none.
    """
    name = path.name
    if name is None or not name.has_suffix(DOCUMENT_SUFFIX):
        return False
    return path != _SKILL_ENTRY_PATH


@total_ordering
@dataclass(frozen=True, slots=True)
class SkillRef:
    """A skill's identity in the workspace model; carries no content.

    Attributes:
        skills_dir: The resolved skills directory the skill is listed in. For an agent's skill it is the resolved
            one, so a skill two agents reach, one of them through a linked skills directory such as
            `.claude/skills`, has one ref.
        entry: The name of the entry in the skills directory, as listed: it may itself be a link to where the
            skill's files live, and the ref still names it here, under the skills directory, which is what makes
            it a skill.
    """

    skills_dir: ResolvedPath
    entry: PathComponent

    @property
    def directory(self) -> RootRelativePath:
        """The skill's directory, `<skills_dir>/<entry>`, root-relative, where an agent reaches it."""
        return self.skills_dir / self.entry

    def __lt__(self, other: object) -> bool:
        """Order refs by directory, the order the model lists them in.

        Ordered by `directory` as a whole, not by skills directory and then entry: a skills directory inside
        another sorts its skills among those of the one holding it, as their paths do.

        Args:
            other: The ref to compare with; anything that is no `SkillRef` is left to Python's reflected comparison.
        """
        if not isinstance(other, SkillRef):
            return NotImplemented
        return self.directory < other.directory

    @property
    def path(self) -> RootRelativePath:
        """Root-relative `<directory>/SKILL.md`; the report path in findings."""
        return self.directory / SKILL_ENTRY

    def find_resource(self, path: SkillRelativePath) -> SkillResourceRef | None:
        """The resource of this skill an agent reaches at `path`, or `None` when a file there is no resource.

        Decided from the name alone, so it asks nothing of the snapshot; see `SkillResourceRef` for which files are
        resources.

        Args:
            path: Where an agent reaches the file, spelled from the skill's directory.
        """
        if not _is_resource_path(path):
            return None
        return SkillResourceRef(self, path)


# order=True so a tuple of locations sorts by ref, the order the model lists the skills in.
@dataclass(frozen=True, slots=True, order=True)
class SkillLocation:
    """Where one skill's files live, as the snapshot the model was loaded from saw them.

    Attributes:
        ref: The skill.
        resolves_to: The resolved directory `ref.directory` leads to, with no symlink on the way. Equal to
            `ref.directory` for a regular directory; the directory the skill's files live in when the entry,
            or a directory on the way to it, is a link, such as `skills/review` for
            `.agents/skills/review -> ../../skills/review`.
        file_resolves_to: The resolved file the skill's `SKILL.md` leads to. `resolves_to / SKILL.md` unless
            that `SKILL.md` is itself a link, and then the file the link leads to, whatever its name.
    """

    ref: SkillRef
    resolves_to: ResolvedPath
    file_resolves_to: ResolvedPath


class NotASkillResourceError(Error):
    """A path inside a skill names no resource: it is the skill's own `SKILL.md`, its directory or not Markdown.

    Attributes:
        path: The rejected path, spelled from the skill's directory.
    """

    path: SkillRelativePath

    def __init__(self, path: SkillRelativePath) -> None:
        self.path = path
        super().__init__(
            f"{str(path)!r} is not a skill resource: it must name a `{DOCUMENT_SUFFIX}` file other than the skill's "
            f'own top-level {SKILL_ENTRY_FILENAME}'
        )


# order=True so a tuple of refs sorts by skill, then by path.
@dataclass(frozen=True, slots=True, order=True)
class SkillResourceRef:
    """A resource's identity: one Markdown file inside a skill; carries no content.

    A valid ref names a file whose name ends in `.md`, and not the skill's own top-level `SKILL.md`.
    `SkillRef.find_resource` asks whether a listed file qualifies.

    Raises:
        NotASkillResourceError: On construction, if `relative_path` is `.`, is not named as a document, or is the
            skill's own top-level `SKILL.md`.

    Attributes:
        skill: The skill the resource belongs to.
        relative_path: The resource where an agent reaches it, spelled from `skill.directory`, every symlink inside
            the skill on the way spelled as the symlink's own name: `guides/d.md` for `shared/guides/d.md` reached
            through `guides -> ../../../shared/guides`.
    """

    skill: SkillRef
    relative_path: SkillRelativePath

    def __post_init__(self) -> None:
        """Keep direct construction from naming a path that is no resource."""
        if not _is_resource_path(self.relative_path):
            raise NotASkillResourceError(self.relative_path)

    @property
    def path(self) -> RootRelativePath:
        """Root-relative `<skill.directory>/<relative_path>`, such as `.agents/skills/review/guides/d.md`.

        The report path in findings. A relative Markdown link in the resource is not read from it: the Agent Skills
        specification has every file of a skill name another by its path from the skill root.
        """
        return self.relative_path.under(self.skill.directory)


@dataclass(frozen=True, slots=True, order=True)
class SkillAliasRef:
    """A path inside a skill reached through a symlink, including a directory alias.

    Attributes:
        skill: The skill whose resource walk found the alias.
        relative_path: Where an agent reaches the alias, spelled from the skill's directory.
    """

    skill: SkillRef
    relative_path: SkillRelativePath

    @property
    def path(self) -> RootRelativePath:
        """Root-relative path at which the alias is reported."""
        return self.relative_path.under(self.skill.directory)


# order=True so a tuple of locations sorts by ref, the order a skill's resources are listed in.
@dataclass(frozen=True, slots=True, order=True)
class SkillResourceLocation:
    """Where one resource of a skill lives, as the snapshot it was listed from saw it.

    Attributes:
        ref: The resource.
        resolves_to: The resolved file `ref.path` leads to, with no symlink on the way. Equal to `ref.path` for a
            file in a regular directory of a skill whose entry is no symlink; the file a symlink leads to, wherever
            it lives, otherwise.
    """

    ref: SkillResourceRef
    resolves_to: ResolvedPath
