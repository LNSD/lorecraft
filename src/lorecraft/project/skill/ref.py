"""A skill's identity in the workspace model, separate from its content and from where its files live.

The model lists which skills exist; the text of a ``SKILL.md`` is not part of it. A ``SkillRef`` is a skill's
key in the model, and its ``path`` is the root-relative location every finding reports. A ``SkillLocation``
records where the skill's directory and its ``SKILL.md`` lead, as the snapshot saw them, so nothing above the
model has to follow a link again to learn it.

The two are kept apart, as an IDE keeps a file's identity apart from the canonical path it resolves to: a link
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
