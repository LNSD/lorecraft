"""One root of a scan's scope: the directory a scan reads, how deep, and whether through symlinks.

It sits apart so that the snapshot can record the scope it was taken of: `scope.py` reads the links the
snapshot module defines, so the snapshot cannot import from it, and the snapshot, the scope query and
`root_expansion.py` all import the root from here. How a root expands through a link is `root_expansion.py`'s,
not this value's.

A root's depth may be unlimited, and that case is decided here and nowhere else: the scan, the scope query and
the root expansion ask a root what it covers, what it lists a level down and whether it is at least as deep as
another, and never decide anything from its depth themselves.
"""

from dataclasses import dataclass

from lorecraft.core.num import UnsignedInt
from lorecraft.core.path import RootRelativePath


@dataclass(frozen=True, slots=True)
class ScanRoot:
    """One directory a snapshot reads, how deep, and whether through symlinks.

    Attributes:
        directory: Root-relative directory the scan starts at.
        depth: 0 lists `directory` only; 1 also lists each DIRECTORY entry inside it, and so on. `None` lists
            every directory below `directory`, at any depth. Entries beyond the depth are listed by their parent
            and never entered.
        follow_links: When true, a symlink that leads somewhere under the root is followed: one on the way
            to `directory`, and one listed by the scan. A link to a directory costs depth as a DIRECTORY
            entry does, and the directory is listed at its resolved path, wherever under the root that is. A
            link to a regular file has the file's bytes read, as a FILE entry has, and recorded at the
            file's resolved path. When false, a symlink is recorded and never followed.
    """

    directory: RootRelativePath
    # `None` rather than a large number, so that a root a level down from an unlimited one is equal to it: that
    # equality is what ends a scan, or the scope query's expansion, that a link back to an ancestor brings round
    # again. A large number would fall by one with each pass and never repeat.
    depth: UnsignedInt | None
    follow_links: bool = False

    def is_covering(self, path: RootRelativePath) -> bool:
        """Whether `path` is an entry the scan of this root lists, by its spelling alone.

        That is an entry of `directory`, or of a directory at most `depth` levels below it, or at any level
        when the depth is unlimited, whether or not it exists. `directory` itself is not one: its parent lists
        it, and the scan only walks to it. Links are not this question, so `follow_links` plays no part;
        `ScopeIndex.is_in_scope` answers for a whole scope, links included.

        Args:
            path: The root-relative entry to ask about, taken as written, with no link on the way followed.
        """
        if path == self.directory or not path.is_relative_to(self.directory):
            return False
        if self.depth is None:
            return True
        return self.listing_level(path) <= self.depth.value

    def listing_level(self, path: RootRelativePath) -> int:
        """How many levels below `directory` the directory listing `path` sits; 0 for an entry of `directory`.

        Args:
            path: A root-relative entry under `directory`, taken as written.
        """
        return len(path.parent.parts) - len(self.directory.parts)

    def find_root_below(self, directory: RootRelativePath, *, levels: int) -> 'ScanRoot | None':
        """The root that lists `directory` with the depth this root has left `levels` levels down.

        The scan lists a DIRECTORY entry of `self.directory` as `find_root_below(entry, levels=1)`, and a directory a
        link leads to with the depth left one level below the link. An unlimited depth stays unlimited
        however far down, and the link policy is kept.

        Args:
            directory: The resolved directory the returned root lists.
            levels: How many levels below `self.directory` that directory is listed, as the scan counts them;
                at least 1.

        Returns:
            The root at `directory`, or `None` when this root's depth runs out before `levels`: the scan
            names the entry and never enters it.
        """
        if self.depth is None:
            return ScanRoot(directory, None, follow_links=self.follow_links)
        depth_left = self.depth.value - levels
        if depth_left < 0:
            return None
        return ScanRoot(directory, UnsignedInt(depth_left), follow_links=self.follow_links)

    def is_at_least_as_deep_as(self, other: 'ScanRoot') -> bool:
        """Whether a scan of this root lists at least as many levels below its directory as one of `other`.

        The scan lists a directory again only when a later root asks for more under it than an earlier one
        listed; this is that comparison, with an unlimited depth deeper than any number. Directory and link
        policy play no part.

        Args:
            other: The root a directory is about to be listed as.
        """
        if self.depth is None:
            return True
        if other.depth is None:
            return False
        return self.depth.value >= other.depth.value
