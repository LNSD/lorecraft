"""Which of the two kinds a skill is: one that serves this repository, or one shipped to others.

The kind is not declared anywhere: it follows from where a skill's files live, which the workspace model
already records, so ``WorkspaceModel.skill_kind`` derives it and nothing stores it.
"""

from enum import Enum


class SkillKind(Enum):
    """Whether a skill serves the repository it sits in or is shipped to other repositories.

    A project skill is one whose entry in a skills directory is a link to a directory outside every skills
    directory an agent reads, such as ``.agents/skills/review -> ../../skills/review``: its files live
    elsewhere in the repository and are linked in, so the repository's own agents run the skill it ships.

    A workspace skill is every other skill: a regular directory inside a skills directory, or a link to a
    directory that is itself inside one, at any depth, such as ``.claude/skills/x -> ../../.agents/skills/x``.
    A skill reached through a linked skills directory, such as ``.claude/skills -> ../.agents/skills``, is
    whatever it is in the directory the link leads to.
    """

    WORKSPACE = 'workspace'
    PROJECT = 'project'
