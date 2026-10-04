"""The identity of a skill and of each of its resources, separate from content and from where their files live.

The model lists which skills exist; the text of a `SKILL.md` is not part of it. A `SkillRef` is a skill's
key in the model, and its `path` is the root-relative location every finding reports. A `SkillLocation`
records where the skill's directory and its `SKILL.md` lead, as the snapshot saw them, so nothing above the
model has to follow a link again to learn it.

A resource, here, is a Markdown file inside a skill other than its own top-level `SKILL.md`, at any depth: the
files the Agent Skills specification places beside `SKILL.md`, as far as they are Markdown. A resource is named
the same way as its skill: a `SkillResourceRef` names it where an agent reaches it, by a `SkillRelativePath`
spelled from the skill's directory, so no ref can name a file outside its skill, and a `SkillResourceLocation`
records the resolved file that path leads to. `SkillRef.find_resource` is where a ref is built: it decides from
the name alone which files are resources.

Each pair keeps a path as an agent names it, its identity, apart from the resolved path it leads to: a link
retargeted to another directory leaves the skill the same skill, named by the same ref, and changes only its
location.
"""

from dataclasses import dataclass
from typing import Final, Self

from lorecraft.agents import SKILL_ENTRY_FILENAME
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

    def __truediv__(self, name: str | PathComponent) -> 'SkillRelativePath':
        """This path joined with `name`, checked again: a `..` or an absolute `name` is rejected.

        Args:
            name: Component, or `/`-separated components, to append below this path. A `PathComponent` names
                a child of this path, so joining one is never rejected.

        Raises:
            RootRelativePathError: If the joined path is absolute or holds a `..` component.
        """
        return SkillRelativePath(self.value / name)

    @property
    def name(self) -> str:
        """The last component, or `''` for the skill's directory."""
        return self.value.name

    def under(self, directory: RootRelativePath) -> RootRelativePath:
        """This path spelled from the root, through the skill directory it is spelled from.

        The one place a path inside a skill becomes root-relative. Neither side is absolute or holds a `..`, so
        neither does the join.

        Args:
            directory: The skill's directory, root-relative, such as `.agents/skills/review`.
        """
        return RootRelativePath(directory.value / self.value.value)


_SKILL_ENTRY: Final[SkillRelativePath] = SkillRelativePath.parse(SKILL_ENTRY_FILENAME)
"""The skill's own top-level `SKILL.md`, spelled from the skill's directory."""


# order=True so a tuple of refs sorts by directory, the order the model lists them in.
@dataclass(frozen=True, slots=True, order=True)
class SkillRef:
    """A skill's identity in the workspace model; carries no content.

    Attributes:
        directory: The skill's directory, `<skills directory>/<skill name>`, root-relative. For an agent's
            skill the skills directory is the resolved one, so a skill two agents reach, one of them through a
            linked skills directory such as `.claude/skills`, has one ref. The last component is the entry as
            listed: it may itself be a link to where the skill's files live, and the ref still names it here,
            under the skills directory, which is what makes it a skill. For a skill in a directory a command
            names, the directory is spelled as the command spelled it, links and all: `skills/review`, or
            `skills` itself when that directory is the skill. So a skill named both ways has two refs.
    """

    directory: RootRelativePath

    @property
    def path(self) -> RootRelativePath:
        """Root-relative ``<directory>/SKILL.md``; the report path in findings."""
        return self.directory / SKILL_ENTRY_FILENAME

    def find_resource(self, path: SkillRelativePath) -> 'SkillResourceRef | None':
        """The resource of this skill an agent reaches at `path`, or `None` when a file there is no resource.

        Decided from the name alone, so it asks nothing of the snapshot: a file is a resource when its name ends
        in the document suffix, `.md`, unless it is the skill's own top-level `SKILL.md`. A `SKILL.md` deeper in
        the skill, such as `examples/SKILL.md`, is a resource. `.`, the skill's directory, has no name, so it is
        none.

        Args:
            path: Where an agent reaches the file, spelled from the skill's directory.
        """
        if not path.name.endswith(DOCUMENT_SUFFIX):
            return None
        if path == _SKILL_ENTRY:
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


# order=True so a tuple of refs sorts by skill, then by path.
@dataclass(frozen=True, slots=True, order=True)
class SkillResourceRef:
    """A resource's identity: one Markdown file inside a skill; carries no content.

    Build one through `SkillRef.find_resource`, which keeps the skill's own top-level `SKILL.md` out; nothing in
    the record itself does.

    Attributes:
        skill: The skill the resource belongs to.
        relative_path: The resource where an agent reaches it, spelled from `skill.directory`, every symlink inside
            the skill on the way spelled as the symlink's own name: `guides/d.md` for `shared/guides/d.md` reached
            through `guides -> ../../../shared/guides`.
    """

    skill: SkillRef
    relative_path: SkillRelativePath

    @property
    def path(self) -> RootRelativePath:
        """Root-relative `<skill.directory>/<relative_path>`, such as `.agents/skills/review/guides/d.md`.

        The report path in findings. A relative Markdown link in the resource is not read from it: the Agent Skills
        specification has every file of a skill name another by its path from the skill root.
        """
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
