"""Lorecraft agents: the model of the coding agents Lorecraft knows.

Everything Lorecraft states about an agent lives in this layer. ``base`` declares the aspects an agent has, one
module each, and every agent has a package of its own stating its values for them: ``claude`` and ``codex``. It
is data: nothing here reads the environment, the home directory or the disk, and it imports no other Lorecraft
layer. Its paths are pure paths relative to the repository root for the project scope, or to the home directory
for the user scope, which whoever holds one resolves.
"""

from .base import (
    UNIVERSAL_PROJECT_AGENTS_MD_FILE,
    UNIVERSAL_PROJECT_SKILLS_DIR,
    UNIVERSAL_USER_SKILLS_DIR,
    Agent,
    AgentName,
    AgentsMdFiles,
    SkillsDirs,
)
from .claude import CLAUDE
from .codex import CODEX

__all__: list[str] = [
    'Agent',
    'AgentName',
    'SkillsDirs',
    'UNIVERSAL_PROJECT_SKILLS_DIR',
    'UNIVERSAL_USER_SKILLS_DIR',
    'AgentsMdFiles',
    'UNIVERSAL_PROJECT_AGENTS_MD_FILE',
    'CLAUDE',
    'CODEX',
]
