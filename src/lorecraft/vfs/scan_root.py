"""One root of a scan's scope: the directory a scan reads, how deep, and whether through symlinks.

It sits apart from `scope.py` and `root_expansion.py` so that the snapshot can record the scope it was taken of:
both read what the snapshot module defines, its links and `MAX_LINKS`, so the snapshot cannot import from them,
and all three import the root from here. How a root expands through a link is `root_expansion.py`'s, not this
value's.
"""

from dataclasses import dataclass

from lorecraft.core.path import RootRelativePath


@dataclass(frozen=True, slots=True)
class ScanRoot:
    """One directory a snapshot reads, how deep, and whether through symlinks.

    Attributes:
        directory: Root-relative directory the scan starts at.
        depth: 0 lists `directory` only; 1 also lists each DIRECTORY entry inside it, and so on. Never
            negative. Entries beyond the depth are listed by their parent and never entered.
        follow_links: When true, a symlink that leads somewhere under the root is followed: one on the way
            to `directory`, and one listed by the scan. A link to a directory costs depth as a DIRECTORY
            entry does, and the directory is listed at its real path, wherever under the root that is. A
            link to a regular file has the file's bytes read, as a FILE entry has, and recorded at the
            file's real path. When false, a symlink is recorded and never followed.
    """

    directory: RootRelativePath
    depth: int
    follow_links: bool = False

    def __post_init__(self) -> None:
        """Reject a negative depth, which would list nothing and read nothing.

        Raises:
            ValueError: If `depth` is negative.
        """
        if self.depth < 0:
            raise ValueError(f'depth must be 0 or more, got {self.depth}')

    def is_covering(self, path: RootRelativePath) -> bool:
        """Whether `path` is an entry the scan of this root lists, by its spelling alone.

        That is an entry of `directory`, or of a directory at most `depth` levels below it, whether or not
        it exists. `directory` itself is not one: its parent lists it, and the scan only walks to it. Links
        are not this question, so `follow_links` plays no part; `is_in_scope` answers for a whole scope,
        links included.

        Args:
            path: The root-relative entry to ask about, taken as written, with no link on the way followed.
        """
        if path == self.directory or not path.is_relative_to(self.directory):
            return False
        return self.listing_level(path) <= self.depth

    def listing_level(self, path: RootRelativePath) -> int:
        """How many levels below `directory` the directory listing `path` sits; 0 for an entry of `directory`.

        Args:
            path: A root-relative entry under `directory`, taken as written.
        """
        return len(path.parent.parts) - len(self.directory.parts)
