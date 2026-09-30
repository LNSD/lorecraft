"""The AGENTS.md files aspect: the files an agent loads as its guide, in a repository and for the user.

The aspect is named after ``AGENTS.md``, the open format most agents read: https://agents.md/. An agent's own
file of the same kind is an AGENTS.md file here whatever it is called: Claude Code's ``CLAUDE.md`` is one.

An agent reads these files in two scopes, and both are declared. The project scope is the files inside a
repository, holding the guide the repository carries, such as ``AGENTS.md``. The user scope is the files under
the user's home directory, holding the user's own instructions, read in every repository.

A file is spelled as a pure path, relative to the root of its scope: the repository root for the project scope,
the home directory for the user one. It names a place and reads nothing. An agent also reads the same filenames
in the directories between the repository root and the one it works in; only the root's are declared. Where an
agent lets an environment variable move its home configuration directory, the default location is what is
declared.
"""

from pathlib import PurePosixPath
from typing import Final

type AgentsMdFiles = tuple[PurePosixPath, ...]
"""The AGENTS.md files one agent reads in one scope, in order of preference. Each agent's constant says what
its order means."""

UNIVERSAL_PROJECT_AGENTS_MD_FILE: Final[PurePosixPath] = PurePosixPath('AGENTS.md')
"""The universal project AGENTS.md file, ``AGENTS.md`` itself as https://agents.md/ defines it, shared by every
agent that reads it as it is. The format is a repository's, so there is no user counterpart: each agent keeps
the user's instructions under its own home configuration directory."""
