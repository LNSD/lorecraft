"""A directory a command names to check the skills in, as the workspace model records it.

An agent reads the skills directories it declares. A command may name any other directory, such as `skills/`,
where a repository keeps the skills its agents' entries link to or the skills it ships to other repositories.
Such a directory is no agent's, so the model records it apart from the agents' skills directories, under the
path the command spelled, which names its skills in every finding.
"""

from dataclasses import dataclass

from lorecraft.core.path import RootRelativePath

from .outside import OutsideSymlink
from .ref import SkillLocation


@dataclass(frozen=True, slots=True)
class NamedDir:
    """A directory a command names, read as one skill or as a directory of skills.

    Attributes:
        path: The directory as the command spelled it, root-relative and unresolved, such as `skills`.
        skills: The location of each skill it holds, named under `path`. That is the directory itself alone
            when a `SKILL.md` is at its root, and otherwise each directory directly inside it holding one,
            sorted, as in an agent's skills directory. Empty when it is neither.
        outside_symlinks: Every symlink of what was named whose chain leaves the repository, sorted by path: the
            path itself when it leads out, the `SKILL.md` at its root, or an entry directly inside it or that
            entry's `SKILL.md`. Each is in the model's `outside_symlinks` too; recorded here as well so the
            directory is known to hold one, which a command reports rather than refuses.
    """

    path: RootRelativePath
    skills: tuple[SkillLocation, ...]
    outside_symlinks: tuple[OutsideSymlink, ...]

    def is_empty(self) -> bool:
        """Whether the directory holds neither a skill nor a symlink leading outside: nothing to check or report."""
        return not self.skills and not self.outside_symlinks
