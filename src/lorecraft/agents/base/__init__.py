"""The aspects Lorecraft declares about a coding agent, one module each, and the record that holds them.

An aspect is one thing an agent decides for itself: its name, where it reads skills, which files it loads as its
guide. This package declares the shape of each; an agent's own package states its values.
"""

from .agent import Agent
from .agents_md import UNIVERSAL_PROJECT_AGENTS_MD_FILE, AgentsMdFiles
from .name import AgentName
from .skills import UNIVERSAL_PROJECT_SKILLS_DIR, UNIVERSAL_USER_SKILLS_DIR, SkillsDirs

__all__: list[str] = [
    'Agent',
    'AgentName',
    'SkillsDirs',
    'UNIVERSAL_PROJECT_SKILLS_DIR',
    'UNIVERSAL_USER_SKILLS_DIR',
    'AgentsMdFiles',
    'UNIVERSAL_PROJECT_AGENTS_MD_FILE',
]
