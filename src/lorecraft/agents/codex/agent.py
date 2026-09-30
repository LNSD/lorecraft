"""Codex, OpenAI's coding agent: its aspects gathered into one record."""

from typing import Final

from lorecraft.agents.base import Agent, AgentName

from .agents_md import CODEX_PROJECT_AGENTS_MD_FILES, CODEX_USER_AGENTS_MD_FILES
from .skills import CODEX_PROJECT_SKILLS_DIRS, CODEX_USER_SKILLS_DIRS

CODEX: Final[Agent] = Agent(
    name=AgentName('codex'),
    project_skills_dirs=CODEX_PROJECT_SKILLS_DIRS,
    user_skills_dirs=CODEX_USER_SKILLS_DIRS,
    project_agents_md_files=CODEX_PROJECT_AGENTS_MD_FILES,
    user_agents_md_files=CODEX_USER_AGENTS_MD_FILES,
)
"""Codex: it reads the universal skills directory in both scopes, ``.agents/skills`` in a repository and
``~/.agents/skills`` for the user, and loads ``AGENTS.md`` as its guide, from the repository and from
``~/.codex`` for the user."""
