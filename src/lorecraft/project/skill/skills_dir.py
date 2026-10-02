"""A skills directory an agent reads in a repository, as the workspace model records it.

Which directories an agent reads is the agent's own statement, in ``lorecraft.agents``. The model records the
ones a repository actually has, each tied to the agent that reads it, so nothing above the model has to ask the
agents again or guess whose a directory is.
"""

from dataclasses import dataclass

from lorecraft.agents import AgentName
from lorecraft.core.path import RootRelativePath
from lorecraft.vfs import ResolvedPath


@dataclass(frozen=True, slots=True)
class SkillsDir:
    """One agent's project skills directory that exists in the repository.

    Attributes:
        agent: The agent that reads the directory.
        path: The directory as the agent declares it, root-relative and unresolved, such as `.claude/skills`.
        resolves_to: The resolved directory `path` leads to, with no symlink on the way. Equal to `path` for a
            regular directory; another agent's directory when this one is a link to it, such as
            `.claude/skills -> ../.agents/skills`.
    """

    agent: AgentName
    path: RootRelativePath
    resolves_to: ResolvedPath
