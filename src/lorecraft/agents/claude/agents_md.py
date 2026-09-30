"""The files Claude Code loads as its guide, in a repository and for the user.

Claude Code's documentation names four locations. Two are modelled here: its project instructions are the
project scope, and its user instructions are the user scope. The managed policy file is the machine's, and
``CLAUDE.local.md`` is one user's uncommitted notes on one repository, not what the repository carries.
"""

from pathlib import PurePosixPath
from typing import Final

from lorecraft.agents.base import UNIVERSAL_PROJECT_AGENTS_MD_FILE, AgentsMdFiles

CLAUDE_PROJECT_AGENTS_MD_FILES: Final[AgentsMdFiles] = (
    UNIVERSAL_PROJECT_AGENTS_MD_FILE,
    PurePosixPath('.claude/AGENTS.md'),
    PurePosixPath('CLAUDE.md'),
    PurePosixPath('.claude/CLAUDE.md'),
)
"""Claude Code reads the universal ``AGENTS.md`` and its own ``CLAUDE.md``, each at the repository root or under
``.claude``. The universal name comes first: it is the one Lorecraft prefers a repository to carry. That is not
the order Claude Code resolves them in: by default it reads ``AGENTS.md`` only in a repository that has no
``CLAUDE.md``.

Reading ``AGENTS.md`` directly requires Claude Code v2.1.277 or later. An earlier version reads ``CLAUDE.md``
files only, and reaches an ``AGENTS.md`` through a ``CLAUDE.md`` that imports it or is a symlink to it."""

CLAUDE_USER_AGENTS_MD_FILES: Final[AgentsMdFiles] = (PurePosixPath('.claude/CLAUDE.md'),)
"""Claude Code reads the user's own instructions from ``~/.claude/CLAUDE.md``."""
