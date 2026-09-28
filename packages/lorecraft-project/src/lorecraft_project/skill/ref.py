"""A skill's identity and location in the workspace model, separate from its content.

The model lists which skills exist, where they really live and which agents see them; the files inside a
skill stay behind the skill repository. One skill can be listed more than once, under the canonical
directory and under an agent's directory, so each listed entry is kept as a ``Sighting``.
"""

from dataclasses import dataclass

from lorecraft_project.layout import SKILL_FILENAME
from lorecraft_vfs import RootRelativePath

from .agent import AgentName
from .name import SkillName


@dataclass(frozen=True, slots=True)
class Sighting:
    """One listed entry that turned out to be this skill.

    Attributes:
        path: Root-relative path of the entry as listed, in the directory that was scanned.
        target: The real root-relative directory the entry leads to; equal to ``path`` for a real directory.
        agents: Every agent that sees the skill through the scanned directory, registry order. For the
            canonical directory that is the universal agents plus any agent whose directory aliases it.
    """

    path: RootRelativePath
    target: RootRelativePath
    agents: tuple[AgentName, ...]


@dataclass(frozen=True, slots=True)
class Skill:
    """One project-scope skill: vercel's ``InstalledSkill`` without ``description`` and ``scope``.

    The path an agent addresses the skill by is ``AgentSkillsDir.path / str(name)``; no record stores it.

    Attributes:
        name: The entry name. The frontmatter ``name`` must equal it; the check reports a mismatch.
        path: Real root-relative directory of the first sighting: under the canonical directory when the
            skill is there, else under the first agent directory in registry order.
        agents: Every agent whose directory exposes the skill, registry order; ``()`` is vercel's "not linked".
        sightings: One per listed entry, scan order (canonical first). A sighting whose ``target`` differs
            from ``path`` is a full copy or a link elsewhere; the check compares their content later.
    """

    name: SkillName
    path: RootRelativePath
    agents: tuple[AgentName, ...]
    sightings: tuple[Sighting, ...]

    @property
    def skill_md(self) -> RootRelativePath:
        """Root-relative ``<path>/SKILL.md``; the report path for frontmatter findings."""
        return self.path / SKILL_FILENAME

    @property
    def is_linked(self) -> bool:
        """vercel's test: at least one agent exposes the skill."""
        return self.agents != ()
