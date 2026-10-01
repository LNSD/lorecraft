"""Skill identity, the skills directories the agents read, and the repository that finds both.

A skill is a document of a special type. It lives outside `docs/`, in a directory of its own under one of the
project skills directories the modelled agents read; its file is always named `SKILL.md`, so the directory
carries its name; and its form is the Agent Skills specification's, not a corpus specification's. Beside its
`SKILL.md` a skill may carry resources, other Markdown files at any depth, each with an identity and a location.
"""

from .ref import SkillLocation, SkillRef, SkillResourceLocation, SkillResourceRef
from .repo import (
    Repository,
    Skill,
    SkillDecodeError,
    SkillDirListError,
    SkillEntryResolveError,
    SkillFileResolveError,
    SkillReadError,
    SkillResource,
    SkillResourceDecodeError,
    SkillResourceReadError,
    SkillResourcesListError,
    SkillResourcesSymlinkResolveError,
    SkillsDirListError,
)
from .skills_dir import SkillsDir

__all__ = [
    'SkillRef',
    'SkillLocation',
    'SkillResourceRef',
    'SkillResourceLocation',
    'SkillsDir',
    'Skill',
    'SkillResource',
    'Repository',
    'SkillsDirListError',
    'SkillEntryResolveError',
    'SkillDirListError',
    'SkillFileResolveError',
    'SkillReadError',
    'SkillDecodeError',
    'SkillResourcesListError',
    'SkillResourcesSymlinkResolveError',
    'SkillResourceReadError',
    'SkillResourceDecodeError',
]
