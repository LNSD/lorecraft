"""Claude Code: everything Lorecraft states about it, one module per aspect ``lorecraft.agents.base`` declares."""

from .agent import CLAUDE
from .agents_md import CLAUDE_PROJECT_AGENTS_MD_FILES, CLAUDE_USER_AGENTS_MD_FILES
from .skills import CLAUDE_PROJECT_SKILLS_DIRS, CLAUDE_USER_SKILLS_DIRS

__all__: list[str] = [
    'CLAUDE',
    'CLAUDE_PROJECT_SKILLS_DIRS',
    'CLAUDE_USER_SKILLS_DIRS',
    'CLAUDE_PROJECT_AGENTS_MD_FILES',
    'CLAUDE_USER_AGENTS_MD_FILES',
]
