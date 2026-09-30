"""One coding agent: the record that holds every aspect Lorecraft declares about it."""

from dataclasses import dataclass

from .agents_md import AgentsMdFiles
from .name import AgentName
from .skills import SkillsDirs


@dataclass(frozen=True, slots=True)
class Agent:
    """One agent, as data: one field per aspect, each declared in its own module beside this one.

    Attributes:
        name: The agent's id, such as ``claude-code``.
        project_skills_dirs: The project skills directories the agent reads, relative to the repository root, in
            order of preference: the universal directory first when the agent reads it.
        user_skills_dirs: The user skills directories the agent reads, relative to the user's home
            directory, in the same order of preference.
        project_agents_md_files: The project AGENTS.md files the agent reads, relative to the
            repository root, in order of preference.
        user_agents_md_files: The user AGENTS.md files the agent reads, relative to the user's home
            directory, in the same order of preference.
    """

    name: AgentName
    project_skills_dirs: SkillsDirs
    user_skills_dirs: SkillsDirs
    project_agents_md_files: AgentsMdFiles
    user_agents_md_files: AgentsMdFiles
