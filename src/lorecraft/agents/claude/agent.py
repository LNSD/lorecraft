"""Claude Code, Anthropic's coding agent: its aspects gathered into one record."""

from typing import Final

from lorecraft.agents.base import Agent, AgentName

from .agents_md import CLAUDE_PROJECT_AGENTS_MD_FILES, CLAUDE_USER_AGENTS_MD_FILES
from .skills import CLAUDE_PROJECT_SKILLS_DIRS, CLAUDE_USER_SKILLS_DIRS

CLAUDE: Final[Agent] = Agent(
    name=AgentName('claude-code'),
    project_skills_dirs=CLAUDE_PROJECT_SKILLS_DIRS,
    user_skills_dirs=CLAUDE_USER_SKILLS_DIRS,
    project_agents_md_files=CLAUDE_PROJECT_AGENTS_MD_FILES,
    user_agents_md_files=CLAUDE_USER_AGENTS_MD_FILES,
)
"""Claude Code: it reads a skills directory of its own in both scopes, ``.claude/skills`` in a repository and
``~/.claude/skills`` for the user, and loads ``CLAUDE.md`` as its guide, from the repository and from
``~/.claude`` for the user."""
