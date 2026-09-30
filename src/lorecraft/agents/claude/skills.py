"""Where Claude Code reads skills, in a repository and for the user."""

from pathlib import PurePosixPath
from typing import Final

from lorecraft.agents.base import SkillsDirs

CLAUDE_PROJECT_SKILLS_DIRS: Final[SkillsDirs] = (PurePosixPath('.claude/skills'),)
"""Claude Code reads a directory of its own and not the universal one, so a repository links that one into it."""

CLAUDE_USER_SKILLS_DIRS: Final[SkillsDirs] = (PurePosixPath('.claude/skills'),)
"""Claude Code reads the user's skills from ``~/.claude/skills``."""
