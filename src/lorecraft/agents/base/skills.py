"""The skills aspect: where an agent reads skills, in a repository and for the user, and the file it enters one by.

An agent reads skills in two scopes, and both are declared. The project scope is the directories inside a
repository, holding the skills the repository carries. The user scope is the directories under the user's
home directory, holding the user's own skills, read in every repository.

A directory is spelled as a pure path, relative to the root of its scope: the repository root for the project
scope, the home directory for the user one. It names a place and reads nothing: resolving it against a
repository or a home directory belongs to whoever holds one. Where an agent lets an environment variable move
its home configuration directory, the default location is what is declared.

A skill is ``<skills directory>/<skill name>/SKILL.md``: a directory directly inside a skills directory, named
for the skill, holding the entry document an agent enters it through. Nothing else is a skill: not a directory
without that document, not one nested deeper, and not one outside every skills directory. The Agent Skills
specification fixes the entry document's filename, https://agentskills.io/specification, so it is declared once
here and no agent states its own.
"""

from pathlib import PurePosixPath
from typing import Final

type SkillsDirs = tuple[PurePosixPath, ...]
"""The skills directories one agent reads in one scope, in order of preference: the universal directory first
when the agent reads it."""

UNIVERSAL_PROJECT_SKILLS_DIR: Final[PurePosixPath] = PurePosixPath('.agents/skills')
"""The canonical project skills directory, shared by every agent that reads it as it is."""

UNIVERSAL_USER_SKILLS_DIR: Final[PurePosixPath] = PurePosixPath('.agents/skills')
"""The canonical user skills directory, ``~/.agents/skills``, shared by every agent that reads it as it is."""

SKILL_ENTRY_FILENAME: Final[str] = 'SKILL.md'
"""The canonical filename of a skill's entry document: the file directly inside a skill directory that makes it
a skill, and the one an agent loads first. The same for every agent and in both scopes."""
