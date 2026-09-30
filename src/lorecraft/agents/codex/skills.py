"""Where Codex reads skills, in a repository and for the user.

Codex's documentation names four locations. Two are modelled here: its repository location is the project
scope, and its user location is the user scope. The admin and system locations are the machine's, not a
repository's or a user's.
"""

from typing import Final

from lorecraft.agents.base import UNIVERSAL_PROJECT_SKILLS_DIR, UNIVERSAL_USER_SKILLS_DIR, SkillsDirs

CODEX_PROJECT_SKILLS_DIRS: Final[SkillsDirs] = (UNIVERSAL_PROJECT_SKILLS_DIR,)
"""Codex reads the universal skills directory of a repository as it is."""

CODEX_USER_SKILLS_DIRS: Final[SkillsDirs] = (UNIVERSAL_USER_SKILLS_DIR,)
"""Codex reads the user's own skills from the universal user directory, ``~/.agents/skills``."""
