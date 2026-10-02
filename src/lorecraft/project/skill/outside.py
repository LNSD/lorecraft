"""A symlink of the skill layout that leads outside the repository, as the snapshot recorded it.

An agent lists its skills directories, the entries in them and the files inside each skill, and the operating
system follows every symlink on the way. One that leads outside the repository loads something the repository
does not hold, so the skill layout records it rather than leaving it out: where an agent reaches it, and where
its chain leaves the root. Both are structure, read from listings and link targets, never from a file's content
and never from outside the root.
"""

from dataclasses import dataclass

from lorecraft.core.path import RootRelativePath
from lorecraft.vfs import RootExit


@dataclass(frozen=True, slots=True)
class OutsideSymlink:
    """One symlink an agent reaches in the skill layout whose chain leaves the repository.

    Attributes:
        path: Where an agent reaches the symlink: a skills directory as the agent declares it, an entry in a real
            skills directory, the `SKILL.md` of that entry, or a path inside a skill, named under the skill's
            entry as a resource is. The link that leaves the root may be this one, one on the way to it, or one
            further along its chain.
        leaves_at: The link the chain left the root through, at its real path, and that link's target as
            recorded.
    """

    path: RootRelativePath
    leaves_at: RootExit
