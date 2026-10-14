"""The files Codex loads as its guide, in a repository and for the user.

In each scope Codex reads only the first file it finds, and the override comes before the file it overrides.
"""

from typing import Final

from lorecraft.agents.base import (
    UNIVERSAL_PROJECT_AGENTS_MD_FILE,
    ProjectAgentsMdFiles,
    ProjectPath,
    UserAgentsMdFiles,
    UserPath,
)
from lorecraft.core.path import RootRelativePath

CODEX_PROJECT_AGENTS_MD_FILES: Final[ProjectAgentsMdFiles] = (
    ProjectPath(RootRelativePath.parse('AGENTS.override.md')),
    UNIVERSAL_PROJECT_AGENTS_MD_FILE,
)
"""Codex reads the universal `AGENTS.md` as it is, unless an `AGENTS.override.md` sits beside it."""

CODEX_USER_AGENTS_MD_FILES: Final[UserAgentsMdFiles] = (
    UserPath(RootRelativePath.parse('.codex/AGENTS.override.md')),
    UserPath(RootRelativePath.parse('.codex/AGENTS.md')),
)
"""Codex reads the user's own instructions from `~/.codex/AGENTS.md`, unless `~/.codex/AGENTS.override.md`
exists."""
