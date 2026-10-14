"""Where Claude Code reads skills, in a repository and for the user."""

from typing import Final

from lorecraft.agents.base import ProjectPath, ProjectSkillsDirs, UserPath, UserSkillsDirs
from lorecraft.core.path import RootRelativePath

CLAUDE_PROJECT_SKILLS_DIRS: Final[ProjectSkillsDirs] = (ProjectPath(RootRelativePath.parse('.claude/skills')),)
"""Claude Code reads a directory of its own and not the universal one, so a repository links that one into it."""

CLAUDE_USER_SKILLS_DIRS: Final[UserSkillsDirs] = (UserPath(RootRelativePath.parse('.claude/skills')),)
"""Claude Code reads the user's skills from `~/.claude/skills`."""
