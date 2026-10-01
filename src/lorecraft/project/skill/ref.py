"""The identity of a skill and of each of its resources, separate from content and from where their files live.

The model lists which skills exist; the text of a `SKILL.md` is not part of it. A `SkillRef` is a skill's
key in the model, and its `path` is the root-relative location every finding reports. A `SkillLocation`
records where the skill's directory and its `SKILL.md` lead, as the snapshot saw them, so nothing above the
model has to follow a link again to learn it.

A resource, here, is a Markdown file inside a skill other than its own top-level `SKILL.md`, at any depth: the
files the Agent Skills specification places beside `SKILL.md`, as far as they are Markdown. A resource is named
the same way as its skill: a `SkillResourceRef` names it where an agent reaches it, under the skill's directory,
and a `SkillResourceLocation` records the real file that path leads to.

Each pair is kept apart, as an IDE keeps a file's identity apart from the canonical path it resolves to: a link
retargeted to another directory leaves the skill the same skill, named by the same ref, and changes only its
location.
"""

from dataclasses import dataclass

from lorecraft.agents import SKILL_ENTRY_FILENAME
from lorecraft.core.path import RootRelativePath


# order=True so a tuple of refs sorts by directory, the order the model lists them in.
@dataclass(frozen=True, slots=True, order=True)
class SkillRef:
    """A skill's identity in the workspace model; carries no content.

    Attributes:
        directory: The skill's directory, ``<skills directory>/<skill name>``, root-relative. The skills
            directory is the real one, so a skill two agents reach, one of them through a linked skills
            directory such as ``.claude/skills``, has one ref. The last component is the entry as listed: it
            may itself be a link to where the skill's files live, and the ref still names it here, under the
            skills directory, which is what makes it a skill.
    """

    directory: RootRelativePath

    @property
    def path(self) -> RootRelativePath:
        """Root-relative ``<directory>/SKILL.md``; the report path in findings."""
        return self.directory / SKILL_ENTRY_FILENAME


# order=True so a tuple of locations sorts by ref, the order the model lists the skills in.
@dataclass(frozen=True, slots=True, order=True)
class SkillLocation:
    """Where one skill's files live, as the snapshot the model was loaded from saw them.

    Attributes:
        ref: The skill.
        resolves_to: The real directory ``ref.directory`` leads to, with no symlink on the way. Equal to
            ``ref.directory`` for a regular directory; the directory the skill's files live in when the entry
            is a link, such as ``skills/review`` for ``.agents/skills/review -> ../../skills/review``.
        file_resolves_to: The real file the skill's ``SKILL.md`` leads to. ``resolves_to / SKILL.md`` unless
            that ``SKILL.md`` is itself a link, and then the file the link leads to, whatever its name.
    """

    ref: SkillRef
    resolves_to: RootRelativePath
    file_resolves_to: RootRelativePath


# order=True so a tuple of refs sorts by skill, then by path.
@dataclass(frozen=True, slots=True, order=True)
class SkillResourceRef:
    """A resource's identity: one Markdown file inside a skill; carries no content.

    Attributes:
        skill: The skill the resource belongs to.
        path: The resource where an agent reaches it, root-relative and under `skill.directory`, every symlink inside
            the skill on the way spelled as the symlink's own name: `.agents/skills/review/guides/d.md` for
            `shared/guides/d.md` reached through `guides -> ../../../shared/guides`. The report path in
            findings, and what a relative Markdown link in the resource is read from.
    """

    skill: SkillRef
    path: RootRelativePath


# order=True so a tuple of locations sorts by ref, the order a skill's resources are listed in.
@dataclass(frozen=True, slots=True, order=True)
class SkillResourceLocation:
    """Where one resource of a skill lives, as the snapshot it was listed from saw it.

    Attributes:
        ref: The resource.
        resolves_to: The real file `ref.path` leads to, with no symlink on the way. Equal to `ref.path` for a
            file in a regular directory of a skill whose entry is no symlink; the file a symlink leads to, wherever
            it lives, otherwise.
    """

    ref: SkillResourceRef
    resolves_to: RootRelativePath
