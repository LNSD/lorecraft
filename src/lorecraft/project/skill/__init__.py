"""Skill identity, the skills directories the agents read, and the repository that finds both.

A skill is a document of a special type. It lives outside ``docs/``, in a directory of its own under one of the
project skills directories the modelled agents read; its file is always named ``SKILL.md``, so the directory
carries its name; and its form is the Agent Skills specification's, not a corpus specification's.
"""

from .ref import SkillRef
from .repo import ListSkillsError, Repository, ResolveSkillsDirError
from .skills_dir import SkillsDir

__all__ = [
    'SkillRef',
    'SkillsDir',
    'Repository',
    'ResolveSkillsDirError',
    'ListSkillsError',
]
