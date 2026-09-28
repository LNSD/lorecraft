"""The agents Lorecraft knows, mirroring vercel-labs/skills' agent registry as data.

A closed set declared in one place (pattern-registry, Pragmatism Caveat): every agent is one ``Agent``
record in ``AGENTS``, and adding an agent is adding one record there. Only the project scope is recorded:
where each agent reads the skills a repository carries. Nothing here reads the environment or the home
directory.
"""

from dataclasses import dataclass
from typing import Final, NewType

from lorecraft_project.layout import UNIVERSAL_SKILLS_DIR
from lorecraft_vfs import RootRelativePath

AgentName = NewType('AgentName', str)  # vercel's AgentType


@dataclass(frozen=True, slots=True)
class Agent:
    """One agent, the project-scope half of vercel's ``AgentConfig`` as data.

    Attributes:
        name: vercel's id, such as ``claude-code``.
        skills_dir: Root-relative project skills directory (vercel ``skillsDir``).
    """

    name: AgentName
    skills_dir: RootRelativePath

    @property
    def is_universal(self) -> bool:
        """vercel's ``isUniversalAgent``: the agent reads the canonical directory itself and needs no link."""
        return self.skills_dir == UNIVERSAL_SKILLS_DIR


# Discovery iterates this tuple, so a repeated name would scan an agent directory twice.
AGENTS: Final[tuple[Agent, ...]] = (
    Agent(name=AgentName('codex'), skills_dir=UNIVERSAL_SKILLS_DIR),
    Agent(name=AgentName('antigravity'), skills_dir=UNIVERSAL_SKILLS_DIR),
    Agent(name=AgentName('opencode'), skills_dir=UNIVERSAL_SKILLS_DIR),
    Agent(name=AgentName('claude-code'), skills_dir=RootRelativePath.parse('.claude/skills')),
)
