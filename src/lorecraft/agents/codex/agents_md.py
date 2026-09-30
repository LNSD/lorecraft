"""The files Codex loads as its guide, in a repository and for the user.

In each scope Codex reads only the first file it finds, and the override comes before the file it overrides.
"""

from pathlib import PurePosixPath
from typing import Final

from lorecraft.agents.base import UNIVERSAL_PROJECT_AGENTS_MD_FILE, AgentsMdFiles

CODEX_PROJECT_AGENTS_MD_FILES: Final[AgentsMdFiles] = (
    PurePosixPath('AGENTS.override.md'),
    UNIVERSAL_PROJECT_AGENTS_MD_FILE,
)
"""Codex reads the universal ``AGENTS.md`` as it is, unless an ``AGENTS.override.md`` sits beside it."""

CODEX_USER_AGENTS_MD_FILES: Final[AgentsMdFiles] = (
    PurePosixPath('.codex/AGENTS.override.md'),
    PurePosixPath('.codex/AGENTS.md'),
)
"""Codex reads the user's own instructions from ``~/.codex/AGENTS.md``, unless ``~/.codex/AGENTS.override.md``
exists."""
