"""A skill's identity in the workspace model, separate from its content.

The model lists which skills exist; the text of a ``SKILL.md`` is not part of it. A ``SkillRef`` is a skill's
key in the model, and its ``path`` is the root-relative location every finding reports.
"""

from dataclasses import dataclass

from lorecraft.agents import SKILL_ENTRY_FILENAME
from lorecraft.vfs import RootRelativePath


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
