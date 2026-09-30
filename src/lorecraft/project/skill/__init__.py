"""Skill identity, the skills directories the agents read, and the repository that finds both.

A skill is a document of a special type. It lives outside ``docs/``, in a directory of its own under one of the
project skills directories the modelled agents read; its file is always named ``SKILL.md``, so the directory
carries its name; and its form is the Agent Skills specification's, not a corpus specification's.
"""

from .ref import SkillLocation, SkillRef
from .repo import GetSkillError, ListSkillsError, Repository, ResolveSkillsDirError, Skill, SkillDecodeError
from .skills_dir import SkillsDir

__all__ = [
    'SkillRef',
    'SkillLocation',
    'SkillsDir',
    'Skill',
    'Repository',
    'ResolveSkillsDirError',
    'ListSkillsError',
    'GetSkillError',
    'SkillDecodeError',
]
